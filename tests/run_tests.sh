#!/usr/bin/env bash
# =============================================================================
# tests/run_tests.sh — Script integral de testing para Jellyfish OS v5.1
#
# Uso:
#   bash tests/run_tests.sh           # Todos los niveles
#   bash tests/run_tests.sh --fast    # Solo unitarios (sin Ollama/RAG)
#   bash tests/run_tests.sh --level 5 # Solo el nivel especificado
# =============================================================================

# Colores
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0; SKIP=0
ONLY_LEVEL=""; FAST_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fast)  FAST_MODE=true ;;
        --level) ONLY_LEVEL="$2"; shift ;;
        --help|-h) echo "Uso: bash tests/run_tests.sh [--fast] [--level N]"; exit 0 ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

[[ -d "venv/bin" ]] && source venv/bin/activate

header() {
    echo ""
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${CYAN}${BOLD}  Nivel $1 — $2${RESET}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}
ok()   { echo -e "  ${GREEN}✅ $*${RESET}"; ((PASS++)); }
fail() { echo -e "  ${RED}❌ $*${RESET}";   ((FAIL++)); }
skip() { echo -e "  ${YELLOW}⏭  SKIP — $*${RESET}"; ((SKIP++)); }
info() { echo -e "  ${YELLOW}ℹ  $*${RESET}"; }

should_run() {
    [[ -z "$ONLY_LEVEL" ]] && return 0
    [[ "$ONLY_LEVEL" == "$1" ]] && return 0
    return 1
}

run_python() {
    # Ejecuta código Python y muestra la salida coloreando ✅ y ❌
    local py_code="$1"
    local out
    out=$(echo "$py_code" | python3 2>&1) || true
    while IFS= read -r line; do
        if [[ "$line" == *"✅"* ]]; then
            echo -e "  ${GREEN}${line}${RESET}"
        elif [[ "$line" == *"❌"* ]]; then
            echo -e "  ${RED}${line}${RESET}"
            ((FAIL++)) || true
        elif [[ -n "$line" ]]; then
            echo "    $line"
        fi
    done <<< "$out"
}

echo ""
echo -e "${BOLD}🪼 Jellyfish OS v5.1 — Suite de Testing${RESET}"
echo -e "${BOLD}   $(date '+%Y-%m-%d %H:%M:%S')${RESET}"

# ===========================================================================
# NIVEL 1 — Sintaxis
# ===========================================================================
if should_run 1; then
    header 1 "Sintaxis y compilación de módulos"
    for mod in jellyfish.py core/state.py core/llm_engine.py core/rag_coder.py \
               core/orchestrator.py core/terminal.py core/plugin_manager.py \
               core/crud.py core/ui.py tests/test_core.py; do
        if [[ ! -f "$mod" ]]; then
            fail "$mod — no encontrado"
            continue
        fi
        out=$(python3 -m py_compile "$mod" 2>&1)
        if [[ -z "$out" ]]; then ok "$mod"
        else fail "$mod — $out"; fi
    done
fi

# ===========================================================================
# NIVEL 2 — pytest
# ===========================================================================
if should_run 2; then
    header 2 "Tests unitarios (pytest)"
    if python3 -m pytest --version &>/dev/null; then
        out=$(python3 -m pytest tests/test_core.py -v --tb=short 2>&1) || true
        while IFS= read -r line; do
            if [[ "$line" == *"PASSED"* ]]; then
                echo -e "  ${GREEN}✅ ${line##*::}${RESET}"
            elif [[ "$line" == *"FAILED"* ]]; then
                echo -e "  ${RED}❌ ${line}${RESET}"
            elif [[ "$line" == *" passed"* ]] || [[ "$line" == *" failed"* ]]; then
                echo -e "  ${BOLD}$line${RESET}"
            fi
        done <<< "$out"
        if echo "$out" | grep -q " passed" && ! echo "$out" | grep -q " failed"; then
            n=$(echo "$out" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' | head -1)
            ok "pytest: ${n:-?} tests pasaron"
        else
            n=$(echo "$out" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -1)
            fail "pytest: ${n:-?} tests fallaron"
        fi
    else
        skip "pytest no instalado — pip install pytest"
    fi
fi

# ===========================================================================
# NIVEL 3 — Ollama
# ===========================================================================
if should_run 3; then
    if [[ "$FAST_MODE" == true ]]; then
        skip "Nivel 3 — omitido en modo rápido"
    else
        header 3 "Conectividad con Ollama"
        OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
        if curl -s --connect-timeout 3 "$OLLAMA_URL/api/tags" &>/dev/null; then
            ok "Ollama responde en $OLLAMA_URL"
            models=$(curl -s "$OLLAMA_URL/api/tags" | \
                python3 -c "import json,sys; d=json.load(sys.stdin); print(','.join(m['name'] for m in d.get('models',[])))" 2>/dev/null || echo "")
            [[ -n "$models" ]] && ok "Modelos: $models" || fail "Sin modelos instalados"

            model_cfg=$(python3 -c "import sys; sys.path.insert(0,'.'); from core.state import MODEL; print(MODEL)" 2>/dev/null || echo "")
            embed_cfg=$(python3 -c "import sys; sys.path.insert(0,'.'); from core.state import EMBED_MODEL; print(EMBED_MODEL)" 2>/dev/null || echo "")
            provider_cfg=$(python3 -c "import sys; sys.path.insert(0,'.'); from core.state import PROVIDER; print(PROVIDER)" 2>/dev/null || echo "")

            if [[ "$provider_cfg" == "ollama" ]]; then
                echo "$models" | tr ',' '\n' | grep -qF "$model_cfg" \
                    && ok "Modelo '$model_cfg' disponible" \
                    || fail "Modelo '$model_cfg' no instalado — ollama pull $model_cfg"
            else
                ok "Modelo '$model_cfg' es de proveedor cloud ($provider_cfg) — no requiere descarga local"
            fi

            echo "$models" | tr ',' '\n' | grep -qF "${embed_cfg%%:*}" \
                && ok "Embed model '$embed_cfg' disponible" \
                || fail "Embed model '$embed_cfg' no instalado — ollama pull $embed_cfg"
        else
            skip "Ollama no responde — ejecuta: ollama serve"
        fi
    fi
fi

# ===========================================================================
# NIVEL 4 — RAG
# ===========================================================================
if should_run 4; then
    if [[ "$FAST_MODE" == true ]]; then
        skip "Nivel 4 — omitido en modo rápido"
    else
        header 4 "Motor RAG (ChromaDB + AST splitter)"
        run_python "
import sys; sys.path.insert(0, '.')
try:
    from core.rag_coder import _dir_hash
    h1 = _dir_hash('/tmp/a'); h2 = _dir_hash('/tmp/a'); h3 = _dir_hash('/tmp/b')
    assert h1 == h2 and h1 != h3
    print(f'✅ Hash determinista y único por proyecto ({h1[:8]}...)')
except Exception as e:
    print(f'❌ Hash test: {e}')

try:
    from core.rag_coder import _RAG_SESSION_UUID, _RAG_OPEN
    assert len(_RAG_SESSION_UUID) == 12 and _RAG_SESSION_UUID in _RAG_OPEN
    print(f'✅ UUID blindado activo ({_RAG_SESSION_UUID})')
except Exception as e:
    print(f'❌ UUID test: {e}')

try:
    from core.rag_coder import _split_python_ast
    code = '''
def suma(a, b):
    return a + b
class Calculadora:
    def mul(self, a, b): return a * b
'''
    chunks = _split_python_ast(code, 'test.py')
    assert chunks and len(chunks) >= 2
    assert any('def suma' in c for c in chunks)
    assert any('class Calculadora' in c for c in chunks)
    print(f'✅ AST splitter OK: {len(chunks)} chunks (función y clase separadas)')
except Exception as e:
    print(f'❌ AST splitter: {e}')

try:
    from core.rag_coder import CodeKnowledgeBase
    from core.state import DB_PATH
    kb = CodeKnowledgeBase(DB_PATH)
    print(f'✅ CodeKnowledgeBase instanciado: {kb.status_text}')
except Exception as e:
    print(f'❌ CodeKnowledgeBase: {e}')
"
    fi
fi

# ===========================================================================
# NIVEL 5 — Seguridad terminal
# ===========================================================================
if should_run 5; then
    header 5 "Seguridad de terminal (lista negra)"
    run_python "
import sys; sys.path.insert(0, '.')
from core.terminal import _is_destructive

casos = [
    ('rm -rf /home/user',           True,  'rm -rf'),
    ('rm -fr /tmp/folder',          True,  'rm -fr'),
    ('rm -Rf /var/log',             True,  'rm -Rf mayúscula'),
    ('sudo rm -rf /*',              True,  'sudo rm -rf /*'),
    ('mkfs.ext4 /dev/sdb1',        True,  'mkfs'),
    ('dd if=/dev/zero of=/dev/sda', True,  'dd a disco'),
    ('chmod -R 777 /',              True,  'chmod 777 raíz'),
    (':(){:|:&};:',                 True,  'fork bomb'),
    ('ls -la /home',               False, 'ls seguro'),
    ('git status',                 False, 'git status'),
    ('pip install httpx',          False, 'pip install'),
    ('rm -f /tmp/archivo.log',     False, 'rm -f específico'),
    ('cat /etc/passwd',            False, 'cat lectura'),
    ('python3 script.py',          False, 'python3'),
]

all_ok = True
for cmd, should_block, desc in casos:
    blocked, _ = _is_destructive(cmd)
    ok_test = blocked == should_block
    if not ok_test: all_ok = False
    sym = '✅' if ok_test else '❌'
    action = 'BLOQUEADO' if blocked else 'PERMITIDO'
    expected = 'OK' if ok_test else ('ESPERABA BLOQUEADO' if should_block else 'ESPERABA PERMITIDO')
    print(f'{sym} {action:10s} ({expected:20s}) | {desc}: \`{cmd[:40]}\`')

print()
print('✅ Todos los casos de seguridad correctos' if all_ok else '❌ HAY FALLOS EN LA LISTA NEGRA')
"
fi

# ===========================================================================
# NIVEL 6 — Sandbox de plugins
# ===========================================================================
if should_run 6; then
    header 6 "Sandbox de plugins"
    run_python "
import os, sys, tempfile; sys.path.insert(0, '.')
from core.plugin_manager import PluginManager

with tempfile.TemporaryDirectory() as tmpdir:
    open(os.path.join(tmpdir,'eco.py'),'w').write('def execute(args):\n    \"\"\"Repite el argumento.\"\"\"\n    return f\"ECO: {args}\"\n')
    open(os.path.join(tmpdir,'roto.py'),'w').write('def execute(args):\n    raise RuntimeError(\"Error intencional\")\n')

    pm = PluginManager(tmpdir)
    print('✅ Sandbox ACTIVO por defecto' if pm._sandbox else '❌ Sandbox no activo')

    r = pm.run_plugin('eco', 'Jellyfish')
    print(f'✅ Plugin normal OK: {r}' if 'ECO: Jellyfish' in r else f'❌ Plugin falló: {r}')

    r2 = pm.run_plugin('roto', '')
    print('✅ Excepción capturada en sandbox' if ('error' in r2.lower() or 'Error' in r2) else f'❌ Excepción no capturada: {r2}')

    r3 = pm.run_plugin('reload', '')
    print('✅ Recarga OK' if 'recargados' in r3.lower() else f'❌ Recarga falló: {r3}')

    listing = pm.list_plugins()
    is_sandbox_tag = any(t in listing.lower() for t in ('sandbox', 'bubblewrap', 'python-isolated'))
    print('✅ Listado con modo sandbox correcto' if 'eco' in listing and is_sandbox_tag else f'❌ Listado incompleto: {listing[:80]}')
"
fi

# ===========================================================================
# NIVEL 7 — Parser del orquestador
# ===========================================================================
if should_run 7; then
    header 7 "Parser JSON del Orquestador"
    run_python "
import sys; sys.path.insert(0, '.')
from core.orchestrator import _parse_plan_safe

tests = [
    ('[{\"query\": \"buscar\"}]',                           1, 'Array JSON plano'),
    ('{\"steps\": [{\"query\": \"a\"}, {\"query\": \"b\"}]}',  2, \"Objeto con 'steps'\"),
    ('{\"plan\": [{\"query\": \"x\"}]}',                    1, \"Objeto con 'plan'\"),
    ('{\"queries\": [{\"query\": \"y\"}]}',                 1, \"Objeto con 'queries'\"),
    ('\`\`\`json\n[{\"query\": \"rag\"}]\n\`\`\`',           1, 'Bloque markdown json'),
    ('\`\`\`\n[{\"query\": \"sin tipo\"}]\n\`\`\`',          1, 'Bloque markdown sin tipo'),
    ('texto [{\"query\": \"paso\"}] extra',                1, 'JSON embebido en texto'),
    ('Lo siento, no puedo.',                              0, 'Texto basura'),
    ('',                                                  0, 'Cadena vacía'),
    ('[{\"step\": \"x\"}, {\"query\": \"v1\"}, {\"query\": \"v2\"}]', 2, 'Filtro clave faltante'),
]

all_ok = True
for text, expected, desc in tests:
    result = _parse_plan_safe(text)
    ok_t = len(result) == expected
    if not ok_t: all_ok = False
    print(f'{\"✅\" if ok_t else \"❌\"} {desc}: {len(result)} paso(s) (esperado {expected})')

print()
print('✅ Todos los formatos JSON parseados correctamente' if all_ok else '❌ FALLOS EN EL PARSER')
"
fi

# ===========================================================================
# RESUMEN
# ===========================================================================
echo ""
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  📊 Resumen — Jellyfish OS v5.1${RESET}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${GREEN}✅ Pasaron : $PASS${RESET}"
echo -e "  ${RED}❌ Fallaron: $FAIL${RESET}"
[[ $SKIP -gt 0 ]] && echo -e "  ${YELLOW}⏭  Omitidos: $SKIP${RESET}"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}🎉 Sistema listo — todos los checks pasaron${RESET}"
    exit 0
else
    echo -e "  ${RED}${BOLD}⚠  Hay $FAIL fallo(s) — revisa los errores arriba${RESET}"
    exit 1
fi
