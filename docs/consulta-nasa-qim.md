# Consulta técnica preparada para NASA GPM

**Estado:** borrador preparado; no enviado. Canal propuesto: [Ask a Question](https://gpm.nasa.gov/data/ask-a-question). El formulario solicita nombre, afiliación, correo y CAPTCHA y pide no incluir enlaces en el mensaje inicial; el equipo debe completar sus datos y decidir el envío.

**Subject:** IMERG V07 monthly quality index: thresholds and regional summaries

**Message:**

Hello GPM team,

We are Bee4TheWorld, a small Costa Rican team developing Iyök, an exploratory MVP for Earth-system trends. We use GPM IMERG Final monthly precipitation, GPM_3IMERGM.07, for 2001–2024, downloaded from NASA GES DISC using CMR and Harmony. Our study region is the largest terrestrial component of a Costa Rican provincial boundary snapshot from IGN/SNIT; separate components are excluded. We use the native 0.1-degree grid and area-weighted cell–polygon intersections.

We would like to explore the monthly precipitationQualityIndex (QIm) without interpreting it as a percentage, actual gauge count, bias estimate, or uncertainty interval. We plan to retain native cell values and report, for each month, area-weighted quantiles and the fraction of the study area represented by valid QIm and precipitation. These would be explicitly labeled as exploratory spatial summaries, not a NASA-endorsed national quality index. We would evaluate their relationship with precipitation errors using independent, quality-controlled gauges where available and identify overlap with GPCC inputs.

The IMERG V07 ATBD (July 2023, section 9.5) lists monthly QIm categories below 3, 3 to below 10, and 10 or above. The IMERG V07 Applications FAQ (February 2025, page 6) instead lists 0–2, 2–4, and 4+. Are these intended for different uses, or is one a correction? For a transparent research baseline we are provisionally using the ATBD intervals at the native-cell level, while preserving continuous values and making no automatic quality filtering decisions.

Would you recommend particular precautions or references for summarizing monthly QIm spatially over an irregular area, and for evaluating whether it predicts local precipitation error? Are there specific limitations of the monthly randomError and QIm fields, gauge dependence, or native grid boundaries that we should prioritize in this test?

Thank you for any clarification. We would be happy to share the detailed method and results in a follow-up.

Bee4TheWorld / Iyök team
