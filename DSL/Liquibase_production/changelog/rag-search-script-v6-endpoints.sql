-- liquibase formatted sql

-- changeset Ruwini:rag-script-v6-changeset1
CREATE TABLE public.mock_endpoints (
    endpoint_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_id      UUID,
    name            VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL,
    type            VARCHAR(50) DEFAULT 'custom_endpoint',
    visibility      VARCHAR(20) DEFAULT 'private',
    method          VARCHAR(10) NOT NULL,
    url             TEXT NOT NULL,
    params          JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mock_endpoints_service_id ON public.mock_endpoints(service_id);
CREATE INDEX idx_mock_endpoints_visibility ON public.mock_endpoints(visibility);

-- changeset Ruwini:rag-script-v6-changeset2
-- Seed data: 3 test endpoints for development and testing

INSERT INTO public.mock_endpoints (name, description, type, visibility, method, url, params)
VALUES (
    'get_public_holidays',
    'Get public holidays for a specific country within a date range',
    'custom_endpoint',
    'public',
    'GET',
    'https://openholidaysapi.org/PublicHolidays',
    '[
        {"name": "countryIsoCode", "type": "string", "required": true,  "description": "ISO 3166-1 alpha-2 country code (e.g. EE for Estonia, DE for Germany)"},
        {"name": "languageIsoCode", "type": "string", "required": false, "description": "ISO language code for the response language (e.g. EE for Estonian, EN for English)"},
        {"name": "validFrom",       "type": "date",   "required": true,  "description": "Start date for holiday lookup in YYYY-MM-DD format"},
        {"name": "validTo",         "type": "date",   "required": true,  "description": "End date for holiday lookup in YYYY-MM-DD format"}
    ]'::jsonb
);

INSERT INTO public.mock_endpoints (name, description, type, visibility, method, url, params)
VALUES (
    'get_current_weather',
    'Get the current weather conditions for a given city',
    'custom_endpoint',
    'public',
    'GET',
    'https://wttr.in',
    '[
        {"name": "city",   "type": "string", "required": true,  "description": "Name of the city to get weather for (e.g. Tallinn, London, Berlin)"},
        {"name": "format", "type": "string", "required": false, "description": "Response format: j1 for JSON, 1 for one-line summary (default: j1)"}
    ]'::jsonb
);

INSERT INTO public.mock_endpoints (name, description, type, visibility, method, url, params)
VALUES (
    'get_exchange_rate',
    'Get the latest currency exchange rate between two currencies',
    'custom_endpoint',
    'public',
    'GET',
    'https://api.frankfurter.app/latest',
    '[
        {"name": "from",   "type": "string", "required": true,  "description": "The base currency code to convert from (e.g. EUR, USD, GBP)"},
        {"name": "to",     "type": "string", "required": true,  "description": "The target currency code to convert to (e.g. USD, EUR, JPY)"},
        {"name": "amount", "type": "number", "required": false, "description": "The amount to convert (default: 1)"}
    ]'::jsonb
);
