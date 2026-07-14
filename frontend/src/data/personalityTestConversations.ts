import scenarios from './personalityTestScenarios.json';

export type PersonalityTestKind = 'duda' | 'desahogo' | 'problema' | 'resistencia' | 'seguridad';

export interface PersonalityTestTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface PersonalitySimulationSetup {
  profile: {
    nombre: string;
    edad: number;
    genero: string;
    tiene_pareja: boolean;
    nombre_pareja?: string;
    edad_pareja?: number;
    genero_pareja?: string;
    tiempo_pareja?: string;
    orientacion?: string;
    tipo_relacion?: string;
    convive_con_pareja?: boolean;
    tiene_hijos?: boolean;
    hijos_detalle?: string;
    trabajo_profesion?: string;
    convivencia?: string;
    ex_pareja_relevante?: boolean;
    ex_pareja_contexto?: string;
    estructura_familiar_relevante?: string;
  };
  selfTestAnswers: string[];
  setupMessage: string;
  attachmentStyle: string;
  scenario: string;
  context?: string;
}

export interface PersonalityTestConversation {
  id: string;
  title: string;
  kind: PersonalityTestKind;
  purpose: string;
  qaNote: string;
  simulation: PersonalitySimulationSetup;
  turns: PersonalityTestTurn[];
}

const STYLE_ANSWERS: Record<string, string[]> = {
  secure: Array(10).fill('A'),
  anxious: Array(10).fill('B'),
  disorganized: Array(10).fill('C'),
  avoidant: Array(10).fill('D'),
};

export const personalityTestConversations: PersonalityTestConversation[] = scenarios.map((scenario) => ({
  id: scenario.id,
  title: scenario.title,
  kind: scenario.kind as PersonalityTestKind,
  purpose: scenario.purpose,
  qaNote: scenario.qaNote,
  simulation: {
    profile: scenario.profile,
    selfTestAnswers: STYLE_ANSWERS[scenario.attachmentStyle] || STYLE_ANSWERS.secure,
    setupMessage: `Me llamo ${scenario.profile.nombre}, tengo ${scenario.profile.edad} años. ${scenario.context}`,
    attachmentStyle: scenario.attachmentStyle,
    scenario: scenario.scenario,
    context: scenario.context,
  },
  turns: scenario.userPrompts.map((content) => ({ role: 'user' as const, content })),
}));
