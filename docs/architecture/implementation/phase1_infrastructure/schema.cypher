// ===== 唯一性约束 =====
CREATE CONSTRAINT book_id_unique IF NOT EXISTS FOR (b:Book) REQUIRE b.book_id IS UNIQUE;
CREATE CONSTRAINT problem_id_unique IF NOT EXISTS FOR (p:Problem) REQUIRE p.problem_id IS UNIQUE;
CREATE CONSTRAINT rootcause_id_unique IF NOT EXISTS FOR (r:RootCause) REQUIRE r.rootcause_id IS UNIQUE;
CREATE CONSTRAINT solution_id_unique IF NOT EXISTS FOR (s:Solution) REQUIRE s.solution_id IS UNIQUE;
CREATE CONSTRAINT exercise_id_unique IF NOT EXISTS FOR (e:Exercise) REQUIRE e.exercise_id IS UNIQUE;
CREATE CONSTRAINT prescription_id_unique IF NOT EXISTS FOR (p:Prescription) REQUIRE p.prescription_id IS UNIQUE;
CREATE CONSTRAINT brainregion_name_unique IF NOT EXISTS FOR (br:BrainRegion) REQUIRE br.name IS UNIQUE;
CREATE CONSTRAINT childprofile_id_unique IF NOT EXISTS FOR (cp:ChildProfile) REQUIRE cp.profile_id IS UNIQUE;
CREATE CONSTRAINT risk_id_unique IF NOT EXISTS FOR (r:Risk) REQUIRE r.risk_id IS UNIQUE;
CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE;
CREATE CONSTRAINT autoentity_name_book_unique IF NOT EXISTS FOR (ae:AutoEntity) REQUIRE (ae.name, ae.book_id) IS UNIQUE;
CREATE CONSTRAINT autocommunity_node_id_unique IF NOT EXISTS FOR (ac:AutoCommunity) REQUIRE ac.node_id IS UNIQUE;

// ===== 索引（加速查询） =====
CREATE INDEX exercise_name_idx IF NOT EXISTS FOR (e:Exercise) ON (e.name);
CREATE INDEX exercise_category_idx IF NOT EXISTS FOR (e:Exercise) ON (e.category);
CREATE INDEX problem_severity_idx IF NOT EXISTS FOR (p:Problem) ON (p.severity);
CREATE INDEX book_title_idx IF NOT EXISTS FOR (b:Book) ON (b.title);
CREATE INDEX childprofile_age_idx IF NOT EXISTS FOR (cp:ChildProfile) ON (cp.age_range_min, cp.age_range_max);
CREATE INDEX exercise_minage_idx IF NOT EXISTS FOR (e:Exercise) ON (e.min_age);
CREATE INDEX autoentity_type_idx IF NOT EXISTS FOR (ae:AutoEntity) ON (ae.entity_type);

// ===== 全文索引（语义搜索） =====
CREATE FULLTEXT INDEX exercise_fulltext IF NOT EXISTS
FOR (e:Exercise) ON EACH [e.name, e.description, e.benefits];

CREATE FULLTEXT INDEX problem_fulltext IF NOT EXISTS
FOR (p:Problem) ON EACH [p.name, p.description, p.symptoms];
