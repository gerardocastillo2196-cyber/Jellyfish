"""tests/test_swarm_architecture.py — Suite de pruebas para el Enjambre Multi-Agente v6.9.15.

Valida:
1. Enrutamiento Inteligente (SwarmRouter): Groq para QA/Crítica vs Gemini para Código/Constructores.
2. Motor de Eventos Pub/Sub Asíncrono (EventBus con asyncio.Queue y apublish).
3. Pizarrón Compartido (Blackboard): Cerrojos duales (threading & asyncio.Lock).
4. El Juez (Circuit Breaker): Límite de debates (MAX_DEBATE_CYCLES = 3) y bloqueo de tareas.
"""

import os
import shutil
import tempfile
import unittest
import asyncio
from unittest.mock import patch, MagicMock

from core.llm_engine import SwarmRouter
from core.event_bus import EventBus, EventType
from core.state import Blackboard
from core.state_proxy import StateProxy, FileLockManager
from core.orchestration.task_runner import TaskRunnerPhase, MAX_DEBATE_CYCLES


class TestSwarmRouter(unittest.TestCase):
    def setUp(self):
        self.state = MagicMock()
        self.state.api_keys = {"groq": "test_groq_key", "gemini": "test_gemini_key"}
        self.state.use_hybrid = True
        self.state.planner_provider = "gemini"
        self.state.planner_model = "gemini-3.6-flash"
        self.state.executor_provider = "gemini"
        self.state.executor_model = "gemini-2.5-pro"

    def test_routing_to_groq_for_qa(self):
        prov, mod = SwarmRouter.route_agent(self.state, agent_name="qa_engineer")
        self.assertEqual(prov, "groq", "El ingeniero QA debe ser enrutado a Groq")
        
        prov_s, _ = SwarmRouter.route_agent(self.state, agent_name="security_auditor")
        self.assertEqual(prov_s, "groq", "Auditor de seguridad debe ser enrutado a Groq para QA")

    def test_custom_qa_model_routing(self):
        # Simulamos configuración expresa proveniente del menú /m para el modelo de QA
        self.state.qa_provider = "openai"
        self.state.qa_model = "gpt-4o-mini"
        prov, mod = SwarmRouter.route_agent(self.state, agent_name="qa_engineer")
        self.assertEqual(prov, "openai")
        self.assertEqual(mod, "gpt-4o-mini")

    @patch.dict("os.environ", {}, clear=True)
    def test_qa_routing_fallback_to_executor(self):
        # Simulamos que no hay configuración de QA y la llave de Groq está ausente
        self.state.qa_provider = None
        self.state.qa_model = None
        self.state.api_keys = {"gemini": "test_gemini_key"}
        self.state.planner_provider = "gemini"
        self.state.planner_model = "gemini-3.6-flash"
        self.state.executor_provider = "ollama"
        self.state.executor_model = "qwen2.5-coder:latest"
        
        prov, mod = SwarmRouter.route_agent(self.state, agent_name="qa_engineer")
        self.assertEqual(prov, "ollama")
        self.assertEqual(mod, "qwen2.5-coder:latest")

    def test_routing_to_gemini_for_developer(self):
        prov, mod = SwarmRouter.route_agent(self.state, agent_name="developer")
        self.assertEqual(prov, "gemini", "El Developer debe usar Gemini por ventana de contexto")
        
        prov_arch, _ = SwarmRouter.route_agent(self.state, agent_name="architect")
        self.assertEqual(prov_arch, "gemini")


class TestAsyncEventBus(unittest.IsolatedAsyncioTestCase):
    async def test_async_pubsub_and_queues(self):
        eb = EventBus()
        queue = eb.subscribe_queue(EventType.CODE_SUBMITTED)
        
        callback_called = False
        async def async_handler(event):
            nonlocal callback_called
            callback_called = True
            self.assertEqual(event.payload.get("developer"), "test_dev")

        eb.subscribe(EventType.CODE_SUBMITTED, async_handler)
        
        event = await eb.apublish(EventType.CODE_SUBMITTED, {"developer": "test_dev", "file": "app.py"})
        self.assertTrue(callback_called, "El suscriptor asíncrono (corrutina) fue ejecutado por apublish")
        
        received_event = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(received_event.type, EventType.CODE_SUBMITTED)
        self.assertEqual(received_event.payload["file"], "app.py")
        eb.unsubscribe_queue(EventType.CODE_SUBMITTED, queue)


class TestBlackboardDualLocks(unittest.IsolatedAsyncioTestCase):
    async def test_async_and_sync_operations(self):
        bb = Blackboard()
        
        # Prueba síncrona
        bb.set("version", "6.9.15")
        self.assertEqual(bb.get("version"), "6.9.15")
        
        # Prueba asíncrona (aset / aget)
        await bb.aset("swarm_status", "active")
        val = await bb.aget("swarm_status")
        self.assertEqual(val, "active")
        
        history = await bb.aget_history("swarm_status")
        self.assertEqual(history, ["active"])


class TestStateProxyFileLockManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.state = MagicMock()
        self.state.active_project = self.test_dir
        self.proxy = StateProxy(self.state)
        
        board_path = os.path.join(self.test_dir, "SPRINT_BOARD.md")
        with open(board_path, "w", encoding="utf-8") as f:
            f.write("| T-001 | Construir API | @developer | TODO |\n| T-002 | Test API | @qa_engineer | TODO |\n")

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir)

    async def test_aread_and_aupdate_board(self):
        content = await self.proxy.aread_project_file("SPRINT_BOARD.md")
        self.assertIn("T-001", content)
        
        success = await self.proxy.aupdate_board_status("T-001", "BLOCKED ⛔")
        self.assertTrue(success)
        
        new_content = await self.proxy.aread_project_file("SPRINT_BOARD.md")
        self.assertIn("BLOCKED (Circuit Breaker)", new_content)


class TestCircuitBreakerJudge(unittest.TestCase):
    def setUp(self):
        self.mock_orch = MagicMock()
        self.mock_orch.state.blackboard = Blackboard()
        self.runner = TaskRunnerPhase(self.mock_orch)

    @patch("core.orchestration.task_runner._call_llm_silent")
    def test_circuit_breaker_tripped(self, mock_call_llm):
        # Simulamos que @qa_engineer rechaza en cada ciclo del debate
        mock_call_llm.return_value = "[REJECTED]\nError en diseño modular."
        
        task_id = "T-777"
        task = {"id": task_id, "status": "IN_PROGRESS", "state": "IN_PROGRESS"}
        tasks = [task]
        
        # Ciclo 1
        ok, reason, breaker = self.runner._run_swarm_consensus_debate(task_id, "developer", "Test task", "app.py", "print('hello')", 1, task, tasks)
        self.assertFalse(ok)
        self.assertFalse(breaker)
        self.assertEqual(self.mock_orch.state.blackboard.get(f"debate_cycles_{task_id}"), 1)
        
        # Ciclo 2
        ok, reason, breaker = self.runner._run_swarm_consensus_debate(task_id, "developer", "Test task", "app.py", "print('hello')", 2, task, tasks)
        self.assertFalse(ok)
        self.assertFalse(breaker)
        self.assertEqual(self.mock_orch.state.blackboard.get(f"debate_cycles_{task_id}"), 2)
        
        # Ciclo 3 (Alcanza MAX_DEBATE_CYCLES -> El Juez interviene)
        ok, reason, breaker = self.runner._run_swarm_consensus_debate(task_id, "developer", "Test task", "app.py", "print('hello')", 3, task, tasks)
        self.assertFalse(ok)
        self.assertTrue(breaker, "El Circuit Breaker (Juez) debe dispararse al alcanzar MAX_DEBATE_CYCLES")
        self.assertEqual(task["status"], "BLOCKED")
        self.assertEqual(self.mock_orch.state.blackboard.get(f"task_status_{task_id}"), "blocked")


if __name__ == "__main__":
    unittest.main()
