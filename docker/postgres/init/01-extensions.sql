-- 首次初始化：启用 pgvector 与 zhparser 中文全文检索
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS zhparser;

-- 中文分词配置：parser=zhparser，简单映射（不依赖词典则按字/词切分）
CREATE TEXT SEARCH CONFIGURATION zh (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION zh ADD MAPPING FOR n,v,a,i,e,l WITH simple;

-- 向量 HNSW 索引所需的函数权限
GRANT ALL ON SCHEMA public TO community;
