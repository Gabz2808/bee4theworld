/** Modelo provisional de presentación; no es el contrato de la API. */
export type Observation = { date: string; value: number | null };
export type Exploration = { kind: "demonstration"; title: string; unit: string; points: Observation[] };
const example: Exploration = {
  kind: "demonstration", title: "Serie de ejemplo", unit: "unidades ilustrativas",
  points: [{date:"2018",value:42},{date:"2019",value:47},{date:"2020",value:44},{date:"2021",value:null},{date:"2022",value:51},{date:"2023",value:48},{date:"2024",value:54}],
};
/** Un adaptador futuro reemplazará esta fuente tras acordar el contrato. */
export async function loadDemonstration(): Promise<Exploration> { return example; }
