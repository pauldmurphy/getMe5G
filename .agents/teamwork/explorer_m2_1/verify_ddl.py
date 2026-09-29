import sqlite3

def test_schema_ddl():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    ddl = """
    CREATE TABLE IF NOT EXISTS brands (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE,
      network_operator TEXT NOT NULL,
      tier_type TEXT NOT NULL,
      logo_url TEXT,
      credit_check_required INTEGER NOT NULL,
      official_signup_url TEXT NOT NULL,
      created_at INTEGER
    );

    CREATE TABLE IF NOT EXISTS plans (
      id TEXT PRIMARY KEY,
      brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
      plan_name TEXT NOT NULL,
      monthly_price REAL NOT NULL,
      autopay_discount_price REAL,
      bundled_price REAL,
      download_min_mbps INTEGER NOT NULL,
      download_max_mbps INTEGER NOT NULL,
      upload_min_mbps INTEGER NOT NULL,
      upload_max_mbps INTEGER NOT NULL,
      equipment_fee REAL NOT NULL DEFAULT 0,
      equipment_upfront_cost REAL NOT NULL DEFAULT 0,
      contract_terms TEXT NOT NULL,
      price_guarantee TEXT
    );

    CREATE TABLE IF NOT EXISTS fcc_provider_mapping (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      frn TEXT NOT NULL,
      provider_id INTEGER NOT NULL,
      brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
      technology_code INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS coordinate_lookup_cache (
      cache_key TEXT PRIMARY KEY,
      address_json TEXT NOT NULL,
      results_json TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_fcc_provider_mapping_frn_tech
      ON fcc_provider_mapping (frn, technology_code);
    CREATE INDEX IF NOT EXISTS idx_plans_brand_id
      ON plans (brand_id);
    CREATE INDEX IF NOT EXISTS idx_coordinate_lookup_cache_expires_at
      ON coordinate_lookup_cache (expires_at);
    """
    
    conn.executescript(ddl)
    
    # Verify tables created
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    assert "brands" in tables
    assert "plans" in tables
    assert "fcc_provider_mapping" in tables
    assert "coordinate_lookup_cache" in tables
    print("Tables verified:", tables)
    
    # Verify brands insertion
    conn.execute("""
    INSERT INTO brands (id, name, slug, network_operator, tier_type, logo_url, credit_check_required, official_signup_url)
    VALUES ('t-mobile-5g-home', 'T-Mobile 5G Home Internet', 't-mobile', 'T-Mobile', 'postpaid', '/logos/t-mobile.svg', 1, 'https://www.t-mobile.com/home-internet');
    """)
    
    # Verify plans insertion with FK
    conn.execute("""
    INSERT INTO plans (id, brand_id, plan_name, monthly_price, autopay_discount_price, bundled_price, download_min_mbps, download_max_mbps, upload_min_mbps, upload_max_mbps, equipment_fee, equipment_upfront_cost, contract_terms, price_guarantee)
    VALUES ('t-mobile-5g-home-standard', 't-mobile-5g-home', 'Standard Unlimited', 60.0, 50.0, 40.0, 72, 245, 15, 31, 0.0, 0.0, 'No annual contract', 'Price Lock Guarantee');
    """)
    
    # Verify FCC mapping insertion
    conn.execute("""
    INSERT INTO fcc_provider_mapping (frn, provider_id, brand_id, technology_code)
    VALUES ('0001565480', 130077, 't-mobile-5g-home', 71);
    """)
    
    # Verify coordinate cache insertion
    conn.execute("""
    INSERT INTO coordinate_lookup_cache (cache_key, address_json, results_json, created_at, expires_at)
    VALUES ('40.7484:-73.9857', '{"lat":40.7484,"lng":-73.9857}', '{"providers":[]}', 1700000000, 1700086400);
    """)
    
    # Verify cascade delete
    conn.execute("DELETE FROM brands WHERE id = 't-mobile-5g-home';")
    cursor.execute("SELECT count(*) FROM plans WHERE brand_id = 't-mobile-5g-home';")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT count(*) FROM fcc_provider_mapping WHERE brand_id = 't-mobile-5g-home';")
    assert cursor.fetchone()[0] == 0
    print("Foreign key cascade delete verified!")
    
    conn.close()
    print("ALL DDL TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_schema_ddl()
