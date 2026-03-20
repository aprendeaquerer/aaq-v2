"""Attachment style test questions and scoring logic - ported from legacy code."""

from typing import Dict, List, Optional

TEST_QUESTIONS = {
    "es": [
        {
            "question": "1. Cuando alguien me cuenta algo personal...",
            "options": [
                {"id": "A", "text": "Me gusta que confien en mi, escucho con calma y conecto con lo que sienten", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Me encanta y enseguida quiero contar mis propias experiencias para sentirnos mas unidos", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "A veces me engancho mucho, otras me siento raro y no se como reaccionar", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Me cuesta, prefiero cambiar de tema o quitarle seriedad con una broma", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "2. Cuando una relacion empieza a ponerse seria o muy cercana...",
            "options": [
                {"id": "A", "text": "Lo vivo con calma, disfruto de la cercania y no siento que tenga que sacrificar mi espacio personal", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Me engancho rapido y quiero pasar todo el tiempo con esa persona, me cuesta soltarla", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Al principio me acerco con muchas ganas, pero luego me agobio y necesito alejarme sin saber bien por que", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Me da miedo tanto compromiso y termino saboteandolo o alejandome para protegerme", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "3. Cuando discuto con alguien importante...",
            "options": [
                {"id": "A", "text": "Confio en que lo podemos hablarlo y resolverlo sin que la relacion sufra", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Lo paso fatal, tengo miedo de que se enfade conmigo y me deje", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Puedo pasar del carino al enfado muy rapido y luego me arrepiento de como reacciono", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Yo no discuto, prefiero irme antes incluso de que la otra persona pueda decir algo", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "4. Si alguien cercano tarda en contestar un mensaje...",
            "options": [
                {"id": "A", "text": "Suelo pensar que estara ocupado/a, confio en la relacion y no me hago lios en la cabeza", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Me pongo inquieto/a, empiezo a darle vueltas y pienso si habre dicho o hecho algo mal", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Primero me preocupo mucho, me siento ignorado/a, luego me enfado y termino alejandome para protegerme", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "No le doy importancia, sigo a lo mio y ni siquiera reviso el movil esperando respuesta", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "5. Cuando tengo que mostrar mi parte vulnerable...",
            "options": [
                {"id": "A", "text": "Lo digo tal cual, confio en que la otra persona lo va a entender", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Lo muestro pero con miedo de que me juzguen o me dejen de lado, y necesito que me tranquilicen para sentirme seguro", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Tan pronto lloro contigo, como no digo ni una palabra, eso depende del dia", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Ni yo mismo termino de entender que significa ser vulnerable, asi que menos aun se como mostrarlo a alguien", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "6. Si alguien me critica o me senala un error...",
            "options": [
                {"id": "A", "text": "Escucho lo que me dice, aunque me incomode, e intento ver si tiene algo de razon", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Me lo tomo muy a pecho, ya no les voy a gustar mas y no me van a querer, me van a abandonar", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "De entrada lo vivo como un ataque, me pongo a la defensiva, y luego me siento mal conmigo mismo/a por haber reaccionado asi", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Me cierro en banda y me digo 'bah, ni caso', pero me queda dando vueltas por que me fastidia bastante", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "7. Cuando pienso en el futuro de mis relaciones...",
            "options": [
                {"id": "A", "text": "Pienso en el futuro lo justo y normal, confio en que si seguimos cuidandonos todo ira bien", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Le doy vueltas todo el tiempo, necesito saber si estaremos juntos o no para poder dormir bien", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "A veces me ilusiono con planes a futuro y otras me entra miedo y quiero salir corriendo", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Yo no pienso en el futuro, prefiero centrarme en lo que estoy viviendo ahora", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "8. Cuando tengo que tomar una decision importante...",
            "options": [
                {"id": "A", "text": "Me tomo mi tiempo, pienso con calma y confio en que pase lo que pase sabre manejarlo", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Me bloqueo y necesito preguntar a otros antes de tomar la decision para estar seguro", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "A veces decido impulsivamente y me tiro al vacio, otras veces se me pasa el tiempo y la oportunidad ya ha pasado", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Decido muy rapido, casi sin pensar y sigo adelante con ello cueste lo que cueste", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "9. Cuando estoy pasando por un momento dificil...",
            "options": [
                {"id": "A", "text": "Entiendo que la vida es asi y que pasara, y si lo necesito, pido ayuda", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Pienso que nunca va a acabar, y me encierro en pensamientos negativos", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Me entra la necesidad de buscar apoyo y las ganas de alejarme de todos", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Me lo guardo, no se lo cuento a nadie y finjo que esta todo perfecto", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
        {
            "question": "10. Cuando alguien nuevo entra en mi vida (amistad, trabajo, grupo)...",
            "options": [
                {"id": "A", "text": "Me adapto facil, hablo con la gente y me integro rapido", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Me entra verguenza, necesito sentir que encajo primero y luego empezar a mostrarme", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "A veces me lanzo con muchas ganas, y al rato me da corte, como si no fuera yo", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
                {"id": "D", "text": "Puedo hablar y participar, pero que no me pregunten demasiado o me ire", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
            ],
        },
    ]
}

PARTNER_TEST_QUESTIONS = {
    "es": [
        {
            "question": "1. Cuando sale el tema de planes a futuro...",
            "options": [
                {"id": "A", "text": "Habla de futuro conmigo de forma natural, sin presionar ni evitar.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Hace mil preguntas y necesita respuestas rapido, se pone nervioso.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Intenta cambiar la conversacion o dice 'ya veremos mas adelante'.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Sus respuestas me confunden: un dia habla de hijos y al otro dice que no quiere relacion seria.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "2. Respecto al tiempo juntos...",
            "options": [
                {"id": "A", "text": "Le encanta estar contigo, pero tambien sabe decir 'hoy me apetece un rato solo'. Equilibra bien.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Quiere estar pegado a ti todo el rato: 'escribeme cuando llegues... mandame foto...'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Prefiere cierta distancia: 'cada uno en su casa' o 'me gusta viajar solo'.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Un dia no se despega de ti, super carinoso, y al siguiente parece frio sin explicacion.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "3. Cuando hay una discusion...",
            "options": [
                {"id": "A", "text": "Dice: 'Vale, hablemos tranquilos y vemos como lo arreglamos'. Busca resolver sin dramatizar.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Se pone nervioso/a: 'No me ignores, dime que estamos bien'. Tiene miedo a que la pelea signifique ruptura.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Se encierra o responde: 'No es para tanto, lo hablamos otro dia'. Evita el conflicto.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Puede explotar con frases fuertes y luego al rato comportarse como si nada.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "4. Cuando le cuentas como te sientes...",
            "options": [
                {"id": "A", "text": "Te escucha y responde: 'Entiendo lo que me dices'. Valida tus emociones.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Se autoculpa: 'Estas enfadado conmigo? Hice algo mal?'. Teme que tus emociones sean rechazo.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Cambia de tema rapido: 'No le des tantas vueltas, vamonos a cenar'. No entra en lo emocional.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "A veces se abre demasiado y al dia siguiente parece que no recuerda nada.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "5. Cuando no contestas rapido a sus mensajes...",
            "options": [
                {"id": "A", "text": "No se preocupa, luego te escribe un 'que tal tu dia?' como si nada.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Se pone ansioso: 'Por que no me contestas? Seguro que estas molesto conmigo'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Lo interpreta como espacio: 'Genial, aprovecho y hago mis cosas'.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Puede enfriarse y devolverte el silencio como forma de castigo.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "6. En su vida social y amistades...",
            "options": [
                {"id": "A", "text": "Te incluye de manera natural: 'Ven, que quiero que conozcas a mis amigos'.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Esta pendiente de si gusta o no, busca aprobacion: 'Crees que les cai bien?'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Prefiere mantenerlo aparte: 'Voy solo, es mejor asi'.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "A veces te presenta como lo mas importante y otras ni siquiera te menciona.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "7. En el trabajo o proyectos personales...",
            "options": [
                {"id": "A", "text": "Comparte: 'Hoy tuve un dia duro' o 'me ascendieron'. No le cuesta mostrarte su mundo.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Siente mucha presion y miedo a fallar: 'Si no hago todo perfecto, me critican'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "No suele contarte: 'Todo bien, nada importante'. Comparte lo justo.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Empieza proyectos con mucha ilusion y de repente los deja sin explicacion.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "8. Durante la intimidad...",
            "options": [
                {"id": "A", "text": "Se nota que busca conexion: te mira, te escucha, disfruta de la cercania.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Lo usa para asegurarse de que lo quieres: 'Despues de hacerlo me siento mas tranquilo contigo'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Puede tener intimidad, pero como algo fisico sin mucha carga emocional.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Puede estar super carinoso en el momento y, de golpe, apartarse.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "9. Cuando se equivoca o mete la pata...",
            "options": [
                {"id": "A", "text": "Dice: 'Perdon, me equivoque. Como lo arreglo?'. Asume y repara.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Se disculpa mil veces: 'Perdona, perdona... me sigues queriendo?'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Lo minimiza: 'No es tan grave, exageras'.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Puede negarlo de entrada y luego al dia siguiente disculparse exageradamente.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
        {
            "question": "10. Como maneja la confianza...",
            "options": [
                {"id": "A", "text": "Confia en ti: no necesita pruebas constantes. Si sales con amigos te dice 'pasalo bien, luego me cuentas'.", "scores": {"secure": 1, "anxious": 0, "disorganized": 0, "avoidant": 0}},
                {"id": "B", "text": "Se pone celoso facilmente: 'Quien te escribio? Seguro que era alguien mas'.", "scores": {"secure": 0, "anxious": 1, "disorganized": 0, "avoidant": 0}},
                {"id": "C", "text": "Desconfia pero de otro modo: 'Si me meto demasiado, pierdo mi libertad'.", "scores": {"secure": 0, "anxious": 0, "disorganized": 0, "avoidant": 1}},
                {"id": "D", "text": "Puede revisarte el movil o sospechar de infidelidades sin razon clara.", "scores": {"secure": 0, "anxious": 0, "disorganized": 1, "avoidant": 0}},
            ],
        },
    ]
}


def calculate_attachment_style(scores: Dict[str, float]) -> str:
    """Return the predominant attachment style from scores."""
    if not scores:
        return "secure"
    max_score = max(scores.values())
    for style in ["secure", "anxious", "avoidant", "disorganized"]:
        if scores.get(style, 0) == max_score:
            return style
    return "secure"


STYLE_DESCRIPTIONS = {
    "es": {
        "secure": "Seguro: Te sientes comodo con la intimidad y la independencia, confias en las relaciones y manejas bien los conflictos.",
        "anxious": "Ansioso: Buscas mucha cercania y te preocupas por el rechazo, necesitas constantemente tranquilidad en las relaciones.",
        "disorganized": "Evitativo temeroso: Tienes patrones contradictorios, a veces buscas cercania y otras te alejas para protegerte.",
        "avoidant": "Evitativo: Prefieres mantener distancia emocional, evitas la intimidad y tiendes a ser independiente.",
    },
    "en": {
        "secure": "Secure: You feel comfortable with intimacy and independence, trust relationships, and handle conflicts well.",
        "anxious": "Anxious: You seek a lot of closeness and worry about rejection, constantly needing reassurance in relationships.",
        "disorganized": "Fearful Avoidant: You have contradictory patterns, sometimes seeking closeness and other times pulling away to protect yourself.",
        "avoidant": "Avoidant: You prefer to maintain emotional distance, avoid intimacy, and tend to be very independent.",
    },
    "ru": {
        "secure": "Надежный: Вам комфортно с близостью и независимостью, вы доверяете отношениям и хорошо справляетесь с конфликтами.",
        "anxious": "Тревожный: Вы ищете много близости и беспокоитесь об отвержении, постоянно нуждаетесь в уверенности в отношениях.",
        "disorganized": "Дезорганизованный: У вас противоречивые модели поведения, иногда вы ищете близость, а иногда отдаляетесь для самозащиты.",
        "avoidant": "Избегающий: Вы предпочитаете эмоциональную дистанцию, избегаете близости и склонны к независимости.",
    },
}


def get_style_description(style: str, language: str = "es") -> str:
    return STYLE_DESCRIPTIONS.get(language, STYLE_DESCRIPTIONS["es"]).get(style, "")


RELATIONSHIP_DYNAMICS = {
    "secure_secure": "secure_secure",
    "anxious_secure": "secure_anxious",
    "avoidant_secure": "secure_avoidant",
    "disorganized_secure": "secure_disorganized",
    "secure_anxious": "secure_anxious",
    "anxious_anxious": "anxious_anxious",
    "avoidant_anxious": "anxious_avoidant",
    "disorganized_anxious": "anxious_disorganized",
    "secure_avoidant": "secure_avoidant",
    "anxious_avoidant": "anxious_avoidant",
    "avoidant_avoidant": "avoidant_avoidant",
    "disorganized_avoidant": "avoidant_disorganized",
    "secure_disorganized": "secure_disorganized",
    "anxious_disorganized": "anxious_disorganized",
    "avoidant_disorganized": "avoidant_disorganized",
    "disorganized_disorganized": "disorganized_disorganized",
}


def calculate_relationship_status(user_style: str, partner_style: str) -> str:
    if not user_style or not partner_style:
        return "unknown"
    key = f"{user_style}_{partner_style}"
    return RELATIONSHIP_DYNAMICS.get(key, "unknown")


RELATIONSHIP_DESCRIPTIONS = {
    "es": {
        "secure_secure": "Relacion segura-segura: Ambos manejan bien la intimidad y la independencia, con comunicacion abierta y resolucion sana de conflictos.",
        "secure_anxious": "Relacion segura-ansiosa: El estilo seguro puede proporcionar estabilidad y tranquilidad al estilo ansioso.",
        "secure_avoidant": "Relacion segura-evitativa: El estilo seguro respeta la necesidad de espacio del evitativo.",
        "secure_disorganized": "Relacion segura-desorganizada: El estilo seguro puede proporcionar consistencia y estabilidad al estilo desorganizado.",
        "anxious_anxious": "Relacion ansiosa-ansiosa: Alta intensidad emocional, pero pueden reforzarse mutuamente las inseguridades.",
        "anxious_avoidant": "Relacion ansiosa-evitativa: Dinamica clasica de persecucion-evitacion.",
        "anxious_disorganized": "Relacion ansiosa-desorganizada: Patrones impredecibles y alta intensidad emocional.",
        "avoidant_avoidant": "Relacion evitativa-evitativa: Ambos mantienen distancia emocional.",
        "avoidant_disorganized": "Relacion evitativa-desorganizada: Patrones contradictorios.",
        "disorganized_disorganized": "Relacion desorganizada-desorganizada: Patrones muy impredecibles y caoticos.",
        "unknown": "Estado de relacion no determinado.",
    },
}


def get_relationship_description(status: str, language: str = "es") -> str:
    return RELATIONSHIP_DESCRIPTIONS.get(language, RELATIONSHIP_DESCRIPTIONS["es"]).get(status, "Estado de relacion no determinado.")
