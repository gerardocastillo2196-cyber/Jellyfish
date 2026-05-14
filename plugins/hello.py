def execute(args):
    """Un plugin de ejemplo que saluda."""
    name = args.strip() if args else "Mundo"
    return f"¡Hola, {name}! El sistema de plugins de Jellyfish está operativo."
