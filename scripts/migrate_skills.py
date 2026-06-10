#!/usr/bin/env python3
"""Script de migración masiva de skills .md a clases Python.

Lee cada archivo .md en skills/*/,  extrae título, agencia,
y contenido de instrucciones, y genera un archivo .py con la clase
correspondiente que hereda de BaseSkill.
"""

import os
import re

SKILLS_DIR = "/run/media/gerardo/22cfa637-7b52-4e19-af43-d03036f6d597/Documentos/Jellyfish/skills"

# Mapeo de keywords por nombre de skill (heurístico por título)
KEYWORD_MAP = {
    "clean_architecture": ["arquitectura", "clean architecture", "solid", "capas", "hexagonal", "onion", "ports adapters"],
    "database_schema_optimization": ["base de datos", "esquema", "sql", "postgresql", "mysql", "mongodb", "índice", "normalización", "query", "orm"],
    "domain_driven_design": ["ddd", "domain driven", "dominio", "bounded context", "aggregate", "entidad", "value object"],
    "microservices_boundary": ["microservicios", "microservice", "bounded context", "servicio", "api gateway", "desacoplar"],
    "tdd_methodology": ["tdd", "test driven", "pruebas", "testing", "red green refactor", "unit test", "pytest", "jest"],
    "code_review_master": ["code review", "revisión de código", "pull request", "PR", "merge request", "refactorización"],
    "graphql_schema_design": ["graphql", "schema", "query", "mutation", "subscription", "resolver", "apollo"],
    "caching_strategies": ["cache", "redis", "memcached", "caching", "ttl", "invalidación", "cdn"],
    "async_messaging": ["kafka", "rabbitmq", "mensajería", "async", "eventos", "pub/sub", "cola", "queue", "streaming"],
    "threat_modeling_stride": ["amenaza", "stride", "threat", "seguridad", "riesgo", "ataque", "vulnerabilidad"],
    "dockerfile_optimization": ["dockerfile", "docker", "contenedor", "imagen", "multi-stage", "build", "capas"],
    "cicd_pipeline_design": ["ci/cd", "pipeline", "github actions", "jenkins", "despliegue", "integración continua"],
    "cloud_cost_optimization": ["cloud", "costo", "aws", "gcp", "azure", "presupuesto", "ahorro", "instancia"],
    "owasp_top_10_audit": ["owasp", "seguridad web", "inyección", "xss", "csrf", "autenticación", "auditoría"],
    "kubernetes_resource_planning": ["kubernetes", "k8s", "pod", "deployment", "service", "helm", "cluster", "recurso"],
    "ui_ux_heuristic_evaluation": ["heurísticas", "nielsen", "usabilidad", "ux", "evaluación", "interfaz"],
    "react_best_practices": ["react", "hooks", "componente", "jsx", "estado", "prop", "virtual dom", "next.js"],
    "a11y_audit": ["accesibilidad", "a11y", "wcag", "aria", "screen reader", "contraste", "alt"],
    "design_system_extractor": ["design system", "tokens", "paleta", "tipografía", "componentes", "figma"],
    "state_management": ["estado", "redux", "zustand", "context", "store", "recoil", "state management"],
    "backlog_grooming": ["backlog", "grooming", "refinamiento", "historia de usuario", "priorización"],
    "sprint_planning": ["sprint", "planificación", "velocidad", "capacidad", "objetivo del sprint"],
    "planning_poker": ["planning poker", "estimación", "puntos de historia", "t-shirt", "fibonacci"],
    "okr_definition": ["okr", "objetivo", "key result", "resultado clave", "meta", "kpi"],
    "risk_matrix_analysis": ["riesgo", "matriz", "impacto", "probabilidad", "mitigación", "contingencia"],
    "seo_technical_audit": ["seo", "auditoría", "sitemap", "robots", "canonical", "meta", "velocidad", "core web vitals"],
    "ab_test_planning": ["a/b test", "experimento", "hipótesis", "variante", "conversión", "significancia"],
    "conversion_rate_optimization": ["conversión", "cro", "embudo", "funnel", "tasa", "landing", "optimización"],
    "viral_loop_design": ["viral", "loop", "referral", "viralidad", "k-factor", "invitación", "compartir"],
    "empathy_mapping": ["empatía", "persona", "usuario", "mapa de empatía", "dolor", "necesidad"],
    "copywriting_pas": ["copywriting", "pas", "problema", "agitación", "solución", "redacción", "venta"],
    "academic_paper_distillation": ["paper", "artículo", "investigación", "académico", "resumen", "abstract"],
    "geopolitical_risk_analysis": ["geopolítica", "riesgo país", "conflicto", "comercio", "regulación"],
    "qualitative_data_coding": ["cualitativo", "codificación", "entrevista", "tema", "categoría", "grounded theory"],
    "statistical_bias_detection": ["sesgo", "bias", "estadística", "distribución", "sampling", "confounders"],
    "historical_precedent_search": ["precedente", "historia", "caso similar", "benchmarking", "analogía"],
    "demographic_trend_analysis": ["demografía", "tendencia", "población", "cohorte", "generacional", "censo"],
    "gdpr_compliance_audit": ["gdpr", "privacidad", "datos personales", "consentimiento", "dpo", "lopd"],
    "open_source_license_check": ["licencia", "open source", "mit", "gpl", "apache", "copyright", "compliance"],
    "saas_pricing_model": ["saas", "pricing", "precio", "modelo de negocio", "freemium", "suscripción", "tier"],
    "cap_table_simulation": ["cap table", "equity", "dilución", "ronda", "inversión", "vesting", "acciones"],
    "sla_drafting": ["sla", "acuerdo de nivel", "uptime", "disponibilidad", "penalización", "contrato"],
    "financial_burn_rate": ["burn rate", "runway", "financiero", "gasto", "presupuesto", "cashflow"],
    "narrative_arc_structuring": ["narrativa", "arco", "historia", "guión", "personaje", "conflicto", "acto"],
    "npc_lore_generation": ["npc", "lore", "personaje", "mundo", "worldbuilding", "backstory", "juego"],
    "game_economy_balancing": ["economía", "balance", "juego", "moneda", "reward", "progresión", "game design"],
    "podcast_escaleta_design": ["podcast", "escaleta", "guión", "episodio", "segmento", "audio"],
    "prompt_engineering_video": ["prompt", "prompt engineering", "video", "ia generativa", "dalle", "midjourney"],
    "brand_voice_consistency": ["marca", "brand voice", "tono", "voz", "consistencia", "identidad"],
}

# Mapeo de subdirectorio a agencia
DIR_TO_AGENCY = {
    "development": "Development",
    "devops": "DevOps",
    "frontend": "Frontend",
    "management": "Management",
    "marketing": "Marketing",
    "research": "Research",
    "legal_media": "Legal & Media",
}


def sanitize_class_name(name: str) -> str:
    """Convierte 'rest_api_design' en 'RestApiDesignSkill'."""
    parts = name.split("_")
    return "".join(p.capitalize() for p in parts) + "Skill"


def extract_content(md_text: str) -> str:
    """Extrae el contenido limpio del .md para get_instructions()."""
    # Quitar las primeras líneas de metadatos (Agencia, Rol Sugerido)
    lines = md_text.strip().splitlines()
    clean_lines = []
    skip_meta = True
    for line in lines:
        if skip_meta:
            stripped = line.strip()
            if stripped.startswith("**Agencia:**") or stripped.startswith("**Rol Sugerido:**"):
                continue
            if stripped.startswith("# "):
                # Primer heading es el titulo, lo convertimos en ##
                clean_lines.append(f"## {stripped[2:]}")
                skip_meta = False
                continue
            skip_meta = False
        clean_lines.append(line)
    return "\n".join(clean_lines)


def extract_title(md_text: str) -> str:
    """Extrae el título del primer heading."""
    for line in md_text.splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return "Unknown Skill"


def generate_skill_py(md_path: str, subdir: str):
    """Genera el archivo .py correspondiente a un .md de skill."""
    filename = os.path.basename(md_path)
    # Quitar número prefix y extensión: "06_clean_architecture.md" -> "clean_architecture"
    base = re.sub(r"^\d+_", "", filename[:-3])
    
    # Si ya existe el .py, saltar
    py_path = os.path.join(os.path.dirname(md_path), f"{base}.py")
    if os.path.exists(py_path):
        print(f"  SKIP (ya existe): {py_path}")
        return
    
    with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
        md_text = f.read()
    
    title = extract_title(md_text)
    content = extract_content(md_text)
    agency = DIR_TO_AGENCY.get(subdir, "default")
    class_name = sanitize_class_name(base)
    keywords = KEYWORD_MAP.get(base, [])
    
    # Escapar triple comillas en el contenido
    content_escaped = content.replace('"""', '\\"\\"\\"')
    
    keywords_str = repr(keywords)
    
    py_code = f'''"""Skill: {title} — Migración automática de {filename}."""
from core.skills.base import BaseSkill


class {class_name}(BaseSkill):
    """{title}."""

    name = "{title}"
    agency = "{agency}"
    keywords = {keywords_str}

    def get_instructions(self) -> str:
        return """{content_escaped}"""
'''
    
    with open(py_path, "w", encoding="utf-8") as f:
        f.write(py_code)
    
    print(f"  ✓ {py_path}")


def main():
    total = 0
    for subdir in sorted(os.listdir(SKILLS_DIR)):
        subdir_path = os.path.join(SKILLS_DIR, subdir)
        if not os.path.isdir(subdir_path):
            continue
        
        md_files = [f for f in sorted(os.listdir(subdir_path)) if f.endswith(".md")]
        if not md_files:
            continue
        
        print(f"\n📁 {subdir}/ ({len(md_files)} skills)")
        
        # Crear __init__.py si no existe
        init_path = os.path.join(subdir_path, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                f.write("")
        
        for md_file in md_files:
            md_path = os.path.join(subdir_path, md_file)
            generate_skill_py(md_path, subdir)
            total += 1
    
    print(f"\n✅ Migración completada: {total} skills procesadas.")


if __name__ == "__main__":
    main()
