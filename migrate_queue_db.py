#!/usr/bin/env python3
"""
Database migration script for hooks-based message queue.
Migrates agent_session to agent_id to support session:window format.
"""

import sqlite3
import argparse
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_table_exists(cursor, table_name):
    """Check if a table exists."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def get_table_columns(cursor, table_name):
    """Get column names for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [col[1] for col in cursor.fetchall()]

def migrate_schema(db_path: str):
    """Migrate the database schema from agent_session to agent_id."""
    db_path_obj = Path(db_path)
    
    # Create database if it doesn't exist
    if not db_path_obj.exists():
        logger.info(f"Creating new database at {db_path}")
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        # Just create the file, sqlite3.connect will handle initialization
        conn = sqlite3.connect(db_path)
        conn.close()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if migration is already applied
        cursor.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cursor.execute("SELECT name FROM migrations WHERE name = 'agent_id_rename'")
        if cursor.fetchone():
            logger.info("Migration already applied.")
            return

        # Check if message_queue table exists
        if not check_table_exists(cursor, 'message_queue'):
            logger.info("Creating new message_queue table with agent_id...")
            create_new_tables(cursor)
        else:
            logger.info("Migrating existing message_queue table...")
            migrate_existing_table(cursor)

        # Record migration
        cursor.execute("INSERT INTO migrations (name) VALUES ('agent_id_rename')")
        conn.commit()
        logger.info("Migration completed successfully.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def create_new_tables(cursor):
    """Create new tables with the correct schema."""
    # Create message_queue table
    cursor.execute("""
    CREATE TABLE message_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        message TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        sequence_number INTEGER NOT NULL DEFAULT 0,
        dependency_id INTEGER,
        project_name TEXT,
        status TEXT DEFAULT 'pending',
        enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        pulled_at TIMESTAMP,
        delivered_at TIMESTAMP,
        delivery_method TEXT DEFAULT 'queued',
        fifo_scope TEXT DEFAULT 'agent',
        FOREIGN KEY (dependency_id) REFERENCES message_queue(id)
    );
    """)

    # Create indexes
    cursor.execute("CREATE INDEX idx_agent_fifo ON message_queue(agent_id, priority DESC, sequence_number);")
    cursor.execute("CREATE INDEX idx_project_fifo ON message_queue(project_name, priority DESC, sequence_number);")
    cursor.execute("CREATE INDEX idx_global_fifo ON message_queue(priority DESC, sequence_number);")

    # Create sequence generator table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sequence_generator (
        name TEXT PRIMARY KEY,
        current_value INTEGER DEFAULT 0
    );
    """)
    cursor.execute("INSERT OR IGNORE INTO sequence_generator (name, current_value) VALUES ('message_sequence', 0);")

    # Create agents table with enhanced fields
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        agent_id TEXT PRIMARY KEY,
        project_name TEXT,
        status TEXT DEFAULT 'active',
        ready_since TIMESTAMP,
        last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        direct_delivery_pipe TEXT,
        last_sequence_delivered INTEGER DEFAULT 0,
        restart_count INTEGER DEFAULT 0,
        last_restart TIMESTAMP,
        last_error TEXT,
        context_preserved TEXT
    );
    """)
    
    # Create agent context table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_context (
        agent_id TEXT PRIMARY KEY,
        last_briefing TIMESTAMP,
        briefing_content TEXT,
        activity_summary TEXT,
        checkpoint_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create session events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        reason TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details TEXT
    );
    """)

def migrate_existing_table(cursor):
    """Migrate existing table by renaming agent_session to agent_id."""
    columns = get_table_columns(cursor, 'message_queue')
    
    if 'agent_session' not in columns:
        logger.info("No migration needed - agent_session column not found")
        return
    
    if 'agent_id' in columns:
        logger.info("No migration needed - agent_id column already exists")
        return

    logger.info("Starting table migration...")

    # Create new table structure
    cursor.execute("""
    CREATE TABLE message_queue_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        message TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        sequence_number INTEGER NOT NULL DEFAULT 0,
        dependency_id INTEGER,
        project_name TEXT,
        status TEXT DEFAULT 'pending',
        enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        pulled_at TIMESTAMP,
        delivered_at TIMESTAMP,
        delivery_method TEXT DEFAULT 'queued',
        fifo_scope TEXT DEFAULT 'agent',
        FOREIGN KEY (dependency_id) REFERENCES message_queue(id)
    );
    """)

    # Copy data, mapping agent_session to agent_id
    # Add sequence numbers for existing records
    cursor.execute("SELECT COUNT(*) FROM message_queue")
    record_count = cursor.fetchone()[0]
    
    if record_count > 0:
        logger.info(f"Migrating {record_count} existing records...")
        cursor.execute("""
        INSERT INTO message_queue_new 
        (id, agent_id, message, priority, sequence_number, dependency_id, project_name, status, 
         enqueued_at, pulled_at, delivered_at, delivery_method, fifo_scope)
        SELECT 
            id, 
            agent_session as agent_id, 
            message, 
            COALESCE(priority, 0), 
            COALESCE(id, 0) as sequence_number,
            dependency_id,
            project_name,
            COALESCE(status, 'pending'),
            COALESCE(enqueued_at, CURRENT_TIMESTAMP),
            pulled_at,
            delivered_at,
            COALESCE(delivery_method, 'queued'),
            COALESCE(fifo_scope, 'agent')
        FROM message_queue;
        """)

    # Drop old table and rename
    cursor.execute("DROP TABLE message_queue;")
    cursor.execute("ALTER TABLE message_queue_new RENAME TO message_queue;")

    # Create indexes
    cursor.execute("CREATE INDEX idx_agent_fifo ON message_queue(agent_id, priority DESC, sequence_number);")
    cursor.execute("CREATE INDEX idx_project_fifo ON message_queue(project_name, priority DESC, sequence_number);")  
    cursor.execute("CREATE INDEX idx_global_fifo ON message_queue(priority DESC, sequence_number);")

    # Create sequence generator if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sequence_generator (
        name TEXT PRIMARY KEY,
        current_value INTEGER DEFAULT 0
    );
    """)
    cursor.execute(f"INSERT OR IGNORE INTO sequence_generator (name, current_value) VALUES ('message_sequence', {record_count});")

    # Migrate agents table if it exists
    if check_table_exists(cursor, 'agents'):
        agents_columns = get_table_columns(cursor, 'agents')
        if 'session_name' in agents_columns and 'agent_id' not in agents_columns:
            logger.info("Migrating agents table...")
            cursor.execute("ALTER TABLE agents RENAME COLUMN session_name TO agent_id;")
            # Update agent_ids to session:window format (assume window 0 for legacy)
            cursor.execute("UPDATE agents SET agent_id = agent_id || ':0' WHERE agent_id NOT LIKE '%:%';")

def add_hooks_enhancements(cursor):
    """Add columns and tables for hooks enhancements."""
    logger.info("Adding hooks enhancement columns and tables...")
    
    # Check and add columns to agents table if they don't exist
    if check_table_exists(cursor, 'agents'):
        columns = get_table_columns(cursor, 'agents')
        
        if 'restart_count' not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN restart_count INTEGER DEFAULT 0;")
            logger.info("Added restart_count column to agents table")
        
        if 'last_restart' not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN last_restart TIMESTAMP;")
            logger.info("Added last_restart column to agents table")
        
        if 'last_error' not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN last_error TEXT;")
            logger.info("Added last_error column to agents table")
        
        if 'context_preserved' not in columns:
            cursor.execute("ALTER TABLE agents ADD COLUMN context_preserved TEXT;")
            logger.info("Added context_preserved column to agents table")
    else:
        # Create agents table if it doesn't exist
        cursor.execute("""
        CREATE TABLE agents (
            agent_id TEXT PRIMARY KEY,
            project_name TEXT,
            status TEXT DEFAULT 'active',
            ready_since TIMESTAMP,
            last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            direct_delivery_pipe TEXT,
            last_sequence_delivered INTEGER DEFAULT 0,
            restart_count INTEGER DEFAULT 0,
            last_restart TIMESTAMP,
            last_error TEXT,
            context_preserved TEXT
        );
        """)
        logger.info("Created agents table with enhanced columns")
    
    # Create agent_context table if it doesn't exist
    if not check_table_exists(cursor, 'agent_context'):
        cursor.execute("""
        CREATE TABLE agent_context (
            agent_id TEXT PRIMARY KEY,
            last_briefing TIMESTAMP,
            briefing_content TEXT,
            activity_summary TEXT,
            checkpoint_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        logger.info("Created agent_context table")
    
    # Create session_events table if it doesn't exist
    if not check_table_exists(cursor, 'session_events'):
        cursor.execute("""
        CREATE TABLE session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        );
        """)
        logger.info("Created session_events table")
    
    # Add missing columns to message_queue if needed
    if check_table_exists(cursor, 'message_queue'):
        columns = get_table_columns(cursor, 'message_queue')
        
        if 'agent_id' not in columns and 'agent_session' not in columns:
            logger.warning("message_queue table has neither agent_id nor agent_session column!")

def main():
    parser = argparse.ArgumentParser(description="Migrate message_queue schema and add hooks enhancements")
    parser.add_argument("--db-path", required=True, help="Path to task_queue.db")
    parser.add_argument("--backup", action="store_true", help="Create backup before migration")
    parser.add_argument("--add-hooks-tables", action="store_true", help="Only add hooks enhancement tables")
    args = parser.parse_args()

    if args.backup:
        backup_path = f"{args.db_path}.backup"
        import shutil
        logger.info(f"Creating backup at {backup_path}")
        shutil.copy2(args.db_path, backup_path)

    if args.add_hooks_tables:
        # Just add hooks tables without full migration
        conn = sqlite3.connect(args.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
            add_hooks_enhancements(cursor)
            cursor.execute("INSERT OR REPLACE INTO migrations (name) VALUES ('hooks_enhancement')")
            conn.commit()
            logger.info("Hooks tables added successfully.")
        except Exception as e:
            logger.error(f"Failed to add hooks tables: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        migrate_schema(args.db_path)

if __name__ == "__main__":
    main()