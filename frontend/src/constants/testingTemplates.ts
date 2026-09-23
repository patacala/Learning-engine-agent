import type { TemporaryDocument } from '../types/testing';

/** Business-context document categories (distinct from training pattern types). */
export interface DocCategory {
  id: string;
  label: string;
}

export const DOC_CATEGORIES: DocCategory[] = [
  { id: 'product', label: 'Product' },
  { id: 'pricing', label: 'Pricing' },
  { id: 'policy', label: 'Policies' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'promotion', label: 'Promotion' },
  { id: 'faq', label: 'FAQ' },
  { id: 'general', label: 'General' },
];

export function docCategoryLabel(id: string): string {
  return DOC_CATEGORIES.find((c) => c.id === id)?.label ?? id;
}

let docCounter = 0;
function docId(): string {
  docCounter += 1;
  return `tmpl-${Date.now()}-${docCounter}`;
}

export interface ScenarioTemplate {
  id: string;
  label: string;
  company_name: string;
  quick_facts: Record<string, string>;
  documents: Omit<TemporaryDocument, 'id'>[];
}

export const SCENARIO_TEMPLATES: ScenarioTemplate[] = [
  {
    id: 'automotive',
    label: 'Car dealership',
    company_name: 'Audi Center',
    quick_facts: {
      modelo_destacado: 'Audi Q5 2026',
      precio_desde: '$52,900',
      financiamiento: 'Desde 4.9% APR a 60 meses',
      garantia: '4 años / 80,000 km',
    },
    documents: [
      {
        title: 'Audi Q5 2026',
        category: 'product',
        content:
          'SUV premium. Motor 2.0 TFSI 261 hp, tracción quattro, techo panorámico, ' +
          'asistente de conducción, pantalla MMI 11.9". Versiones: Premium, Premium Plus, Prestige.',
      },
      {
        title: 'Lista de precios',
        category: 'pricing',
        content:
          'Q5 Premium: $52,900. Premium Plus: $57,300. Prestige: $61,800. ' +
          'Paquete Black Optic +$1,200. Enganche mínimo 20%.',
      },
      {
        title: 'Promoción del mes',
        category: 'promotion',
        content:
          'Test drive con obsequio. 0% de interés los primeros 12 meses en modelos 2025 seleccionados. ' +
          'Bono de $2,000 por entrega de auto usado.',
      },
      {
        title: 'Política de garantía y devolución',
        category: 'policy',
        content:
          'Garantía de fábrica 4 años / 80,000 km. Mantenimiento incluido primeros 2 años. ' +
          'Devolución no aplica en unidades nuevas ya matriculadas.',
      },
    ],
  },
  {
    id: 'saas',
    label: 'SaaS B2B',
    company_name: 'FlowCRM',
    quick_facts: {
      plan_popular: 'Pro',
      precio_pro: '$49/usuario/mes',
      trial: '14 días gratis',
      soporte: '24/7 en plan Enterprise',
    },
    documents: [
      {
        title: 'Planes y precios',
        category: 'pricing',
        content:
          'Starter: $19/usuario/mes. Pro: $49/usuario/mes. Enterprise: a medida. ' +
          'Facturación anual con 2 meses gratis.',
      },
      {
        title: 'Funcionalidades Pro',
        category: 'product',
        content:
          'Automatizaciones ilimitadas, reportes avanzados, integraciones (Slack, Zapier), ' +
          'roles y permisos, API completa.',
      },
      {
        title: 'Política de prueba y cancelación',
        category: 'policy',
        content:
          'Trial de 14 días sin tarjeta. Cancelación en cualquier momento. ' +
          'Reembolso prorrateado en planes anuales dentro de los primeros 30 días.',
      },
    ],
  },
  {
    id: 'realestate',
    label: 'Real estate',
    company_name: 'Nova Propiedades',
    quick_facts: {
      zona_destacada: 'Zona Norte',
      precio_m2: '$2,400/m²',
      proceso: 'Reserva 5%, firma 30 días',
    },
    documents: [
      {
        title: 'Departamentos disponibles',
        category: 'inventory',
        content:
          'Torre Vista: 1-3 dormitorios, 45-120 m². Entrega inmediata. ' +
          'Amenities: piscina, gimnasio, coworking, seguridad 24/7.',
      },
      {
        title: 'Precios y financiamiento',
        category: 'pricing',
        content:
          'Desde $108,000 (1 dorm) hasta $288,000 (3 dorm). ' +
          'Financiamiento directo hasta 15 años. Reserva con 5%.',
      },
      {
        title: 'Proceso de compra',
        category: 'faq',
        content:
          'Reserva, evaluación crediticia, firma de promesa (30 días), escrituración. ' +
          'Se aceptan permutas y crédito hipotecario bancario.',
      },
    ],
  },
];

export function instantiateTemplate(tmpl: ScenarioTemplate): TemporaryDocument[] {
  return tmpl.documents.map((d) => ({ ...d, id: docId() }));
}

export { docId };
