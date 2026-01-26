CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source VARCHAR(100) NOT NULL,
    author VARCHAR(255),
    published_date TIMESTAMP NOT NULL,
    content TEXT,
    word_count INTEGER,
    categories TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS queries (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_articles_published ON articles(published_date DESC);
CREATE INDEX idx_articles_source ON articles(source);

CREATE DATABASE airflow;
