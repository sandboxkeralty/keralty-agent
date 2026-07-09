"""Predefined organization-wide writing styles.

Shipped in code (not Firestore) so they need no seeding/migration and can't be
edited or deleted through the API — the router rejects writes to "preset:*" ids.
Guides are written in second-person imperative Spanish so they drop directly
into an agent instruction via the {writing_style?} placeholder.
"""

PRESETS: list = [
    {
        "style_id": "preset:formal",
        "name": "Formal corporativo",
        "description": "Registro alto y protocolar para comunicaciones oficiales y externas.",
        "source": "preset",
        "style_guide": (
            "- Trata al lector de usted en todo momento; nunca tutees.\n"
            "- Mantén un registro alto y protocolar: evita coloquialismos, anglicismos y contracciones.\n"
            "- Abre con un saludo formal (\"Estimado/a...\") y cierra con una despedida protocolar "
            "(\"Cordialmente\", \"Atentamente\").\n"
            "- Redacta en párrafos completos y bien conectados; usa viñetas solo para enumeraciones largas.\n"
            "- Cierra siempre con próximos pasos o compromisos formulados de manera formal.\n"
            "- Prefiere frases completas y subordinadas bien construidas sobre frases telegráficas."
        ),
    },
    {
        "style_id": "preset:directo",
        "name": "Ejecutivo directo",
        "description": "Conclusión primero, frases cortas, máxima densidad de información.",
        "source": "preset",
        "style_guide": (
            "- Empieza SIEMPRE por la conclusión o recomendación (estilo BLUF: bottom line up front).\n"
            "- Frases cortas, una idea por frase. Párrafos de 2-3 líneas máximo.\n"
            "- Usa viñetas y negrita para destacar cifras, decisiones y acciones requeridas.\n"
            "- Elimina preámbulos, fórmulas de cortesía extensas y contexto innecesario.\n"
            "- El documento o correo completo debe caber en una pantalla; si no cabe, resume más.\n"
            "- Termina con una lista explícita de acciones: quién, qué, cuándo."
        ),
    },
    {
        "style_id": "preset:cercano",
        "name": "Cercano y empático",
        "description": "Tono cálido y humano, tuteo, lenguaje claro sin jerga corporativa.",
        "source": "preset",
        "style_guide": (
            "- Tutea al lector y usa un tono cálido, cercano y humano.\n"
            "- Reconoce el contexto y el esfuerzo de las personas antes de entrar en materia.\n"
            "- Evita la jerga corporativa y los tecnicismos; explica con palabras sencillas.\n"
            "- Usa ejemplos concretos y un lenguaje positivo, orientado a soluciones.\n"
            "- Cierra con una despedida personal y una invitación genuina a conversar "
            "(\"Cuenta conmigo\", \"Quedo pendiente de tus comentarios\").\n"
            "- Mantén la calidez sin perder claridad: la amabilidad no sustituye la precisión."
        ),
    },
    {
        "style_id": "preset:institucional",
        "name": "Comunicado institucional",
        "description": "Voz institucional de Keralty para anuncios y comunicados oficiales.",
        "source": "preset",
        "style_guide": (
            "- Redacta en tercera persona o en voz institucional (\"Keralty informa...\", \"La organización...\").\n"
            "- Tono neutro, sobrio y sin opiniones personales.\n"
            "- Estructura fija de comunicado: contexto breve → anuncio principal → implicaciones "
            "para los destinatarios → canal de contacto para dudas.\n"
            "- Usa terminología institucional del sector salud con precisión.\n"
            "- Evita signos de exclamación, humor y adjetivos valorativos.\n"
            "- Incluye fechas y responsables de forma explícita cuando existan."
        ),
    },
]

PRESETS_BY_ID = {p["style_id"]: p for p in PRESETS}
