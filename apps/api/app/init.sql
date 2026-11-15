BEGIN;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;

CREATE TABLE public.variables (
    id text PRIMARY KEY,
    name text NOT NULL,
    source text NOT NULL,
    description text,
    unit text NOT NULL,
    temporal_resolution text NOT NULL
        CHECK (temporal_resolution IN ('monthly')),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.variables (
    id,
    name,
    source,
    description,
    unit,
    temporal_resolution
)
VALUES (
    'precipitation',
    'Precipitación mensual estimada',
    'NASA GPM IMERG Final Run',
    'Estimación satelital combinada GPM IMERG; no representa una medición puntual de estación.',
    'mm/month',
    'monthly'
)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE public.regions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    description text,
    geom extensions.geometry(Polygon, 4326) NOT NULL,
    boundary_source text NOT NULL,
    boundary_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT regions_geom_valid CHECK (extensions.st_isvalid(geom))
);

CREATE TABLE public.ingestion_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id uuid NOT NULL REFERENCES public.regions(id) ON DELETE RESTRICT,
    variable_id text NOT NULL REFERENCES public.variables(id) ON DELETE RESTRICT,
    requested_start date NOT NULL,
    requested_end date NOT NULL,
    dataset_id text NOT NULL,
    dataset_version text NOT NULL,
    source_units text NOT NULL,
    output_units text NOT NULL,
    unit_conversion text NOT NULL,
    spatial_resolution_degrees numeric NOT NULL
        CHECK (spatial_resolution_degrees > 0),
    weighting_method text NOT NULL,
    source_granule_ids text[] NOT NULL
        CHECK (cardinality(source_granule_ids) > 0),
    region_geometry_snapshot extensions.geometry(Polygon, 4326) NOT NULL,
    region_source_snapshot text NOT NULL,
    region_version_snapshot text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ingestion_runs_month_start
        CHECK (date_trunc('month', requested_start)::date = requested_start),
    CONSTRAINT ingestion_runs_month_end
        CHECK ((requested_end + 1) = date_trunc('month', requested_end + 1)::date),
    CONSTRAINT ingestion_runs_date_order
        CHECK (requested_end >= requested_start)
);

CREATE TABLE public.processed_data (
    ingestion_run_id uuid NOT NULL
        REFERENCES public.ingestion_runs(id) ON DELETE CASCADE,
    observed_month date NOT NULL,
    precipitation_mm double precision,
    coverage_fraction double precision NOT NULL
        CHECK (coverage_fraction >= 0 AND coverage_fraction <= 1),
    quality_flag text NOT NULL,
    PRIMARY KEY (ingestion_run_id, observed_month),
    CONSTRAINT processed_data_month_start
        CHECK (date_trunc('month', observed_month)::date = observed_month),
    CONSTRAINT processed_data_nonnegative
        CHECK (precipitation_mm IS NULL OR precipitation_mm >= 0),
    CONSTRAINT processed_data_quality
        CHECK (
            (quality_flag = 'ok'
                AND precipitation_mm IS NOT NULL
                AND coverage_fraction = 1)
            OR (quality_flag = 'partial_coverage'
                AND precipitation_mm IS NOT NULL
                AND coverage_fraction > 0
                AND coverage_fraction < 1)
            OR (quality_flag = 'missing_value'
                AND precipitation_mm IS NULL)
            OR (quality_flag = 'missing_month'
                AND precipitation_mm IS NULL
                AND coverage_fraction = 0)
        )
);

CREATE INDEX regions_geom_idx
    ON public.regions USING GIST (geom);

CREATE INDEX ingestion_runs_region_variable_period_idx
    ON public.ingestion_runs (region_id, variable_id, requested_start, requested_end);

CREATE INDEX processed_data_observed_month_idx
    ON public.processed_data (observed_month);

ALTER TABLE public.variables ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processed_data ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    role_name text;
    app_tables text :=
        'public.variables, public.regions, public.ingestion_runs, public.processed_data';
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE %s FROM %I',
                app_tables,
                role_name
            );
        END IF;
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        GRANT USAGE ON SCHEMA public TO service_role;
        GRANT USAGE ON SCHEMA extensions TO service_role;
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %s TO service_role',
            app_tables
        );
    END IF;
END
$$;

COMMIT;
