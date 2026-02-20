-- Database migration script for CI/CD Pipeline Healer
-- Run this script to create all required tables

-- Create teams table
CREATE TABLE IF NOT EXISTS public.teams (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL,
    team_name text NOT NULL,
    leader_name text NOT NULL,
    branch_name text NOT NULL UNIQUE,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT teams_pkey PRIMARY KEY (id),
    CONSTRAINT teams_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.profiles(id)
);

-- Create profiles table
CREATE TABLE IF NOT EXISTS public.profiles (
    id uuid NOT NULL,
    email text,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT profiles_pkey PRIMARY KEY (id),
    CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

-- Create runs table
CREATE TABLE IF NOT EXISTS public.runs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    team_id uuid NOT NULL,
    repo_url text NOT NULL,
    status text NOT NULL CHECK (status = ANY (ARRAY['PENDING'::text, 'RUNNING'::text, 'PASSED'::text, 'FAILED'::text])),
    total_failures integer DEFAULT 0,
    total_fixes integer DEFAULT 0,
    iterations_used integer DEFAULT 0,
    total_time_seconds integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT runs_pkey PRIMARY KEY (id),
    CONSTRAINT runs_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id)
);

-- Create ci_timeline table
CREATE TABLE IF NOT EXISTS public.ci_timeline (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL,
    iteration_number integer NOT NULL,
    status text NOT NULL CHECK (status = ANY (ARRAY['PASSED'::text, 'FAILED'::text])),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT ci_timeline_pkey PRIMARY KEY (id),
    CONSTRAINT ci_timeline_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.runs(id)
);

-- Create fixes table
CREATE TABLE IF NOT EXISTS public.fixes (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL,
    file text NOT NULL,
    bug_type text NOT NULL CHECK (bug_type = ANY (ARRAY['LINTING'::text, 'SYNTAX'::text, 'LOGIC'::text, 'TYPE_ERROR'::text, 'IMPORT'::text, 'INDENTATION'::text])),
    line_number integer,
    commit_message text,
    status text NOT NULL CHECK (status = ANY (ARRAY['FIXED'::text, 'FAILED'::text])),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT fixes_pkey PRIMARY KEY (id),
    CONSTRAINT fixes_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.runs(id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_runs_team_id ON public.runs(team_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON public.runs(status);
CREATE INDEX IF NOT EXISTS idx_ci_timeline_run_id ON public.ci_timeline(run_id);
CREATE INDEX IF NOT EXISTS idx_fixes_run_id ON public.fixes(run_id);
CREATE INDEX IF NOT EXISTS idx_teams_branch_name ON public.teams(branch_name);
