import os

AGENCY_DIR = os.path.expanduser("~/MisModelosIA/agencia")
MODEL = os.getenv("JELLYFISH_MODEL", "qwen2.5-agent:latest")
OLLAMA_URL = "http://localhost:11434/api/chat"

class JellyfishState:
    def __init__(self):
        self.active_agent = "default"
        self.active_skills = set()
        self.context_files = set()
        self.history = [] # Charla activa (Sliding Window)
        self.static_history = [] # Core Context
        self.system_prompt = ""
        self.load_agent("default")

    def load_agent(self, agent_name):
        self.active_agent = agent_name.lower()
        template_file = f"{AGENCY_DIR}/agents/template.md"
        agent_file = f"{AGENCY_DIR}/agents/{self.active_agent}.md"
        
        # 1. Cargar Protocolo Maestro (Herencia)
        self.system_prompt = ""
        if os.path.exists(template_file):
            try:
                with open(template_file, "r") as f:
                    self.system_prompt = f"[PROTOCOLO MAESTRO]\n{f.read()}\n\n"
            except: pass

        # 2. Cargar Perfil Específico
        if self.active_agent == "default":
            self.system_prompt += "Eres Jellyfish, un asistente técnico avanzado. Tienes acceso a la terminal y puedes analizar resultados de comandos."
        else:
            if os.path.exists(agent_file):
                try:
                    with open(agent_file, "r") as f:
                        self.system_prompt += f"[PERFIL ESPECÍFICO DE @{self.active_agent.upper()}]\n{f.read()}"
                except Exception as e:
                    print(f"Error al cargar agente: {e}")
        
        self.history = [] 
        self.refresh_static_context()

    def refresh_static_context(self):
        """Prepara el contexto inamovible (System + Skills + Contexto)"""
        self.static_history = [{"role": "system", "content": self.system_prompt}]
        
        # 3. Cargar Protocolo Maestro de Habilidades (Herencia)
        skill_template = f"{AGENCY_DIR}/skills/template.md"
        if os.path.exists(skill_template):
            try:
                with open(skill_template, "r") as f:
                    self.static_history.append({"role": "system", "content": f"[PROTOCOLO DE HABILIDADES]\n{f.read()}"})
            except: pass

        for skill_path in self.active_skills:
            if "template.md" in skill_path: continue # Evitar duplicados
            try:
                with open(skill_path, "r") as f:
                    self.static_history.append({"role": "system", "content": f"[SKILL]\n{f.read()}"})
            except: pass
        
        for f in self.context_files:
            try:
                if os.path.isfile(f):
                    with open(f, "r") as file: 
                        self.static_history.append({"role": "system", "content": f"[ARCHIVO]\n{file.read()}"})
            except: pass

    def get_full_history(self):
        """Sliding Window de 20 mensajes de charla"""
        return self.static_history + self.history[-20:]

    def reset_history(self):
        self.history = []
        self.refresh_static_context()
