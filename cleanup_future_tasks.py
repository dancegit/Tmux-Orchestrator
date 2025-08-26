#!/usr/bin/env python3
"""Cleanup script to remove far-future one-time tasks"""

import sqlite3
import time

conn = sqlite3.connect('task_queue.db')
cursor = conn.cursor()

now = time.time()
one_year_from_now = now + 31536000  # 1 year

# Delete one-time tasks scheduled more than 1 year in the future
cursor.execute("""
    DELETE FROM tasks 
    WHERE next_run > ? AND interval_minutes = 0
""", (one_year_from_now,))

deleted = cursor.rowcount
conn.commit()

print(f"Deleted {deleted} future one-time tasks")

# Also show some statistics
cursor.execute("SELECT COUNT(*) FROM tasks WHERE next_run > ?", (one_year_from_now,))
remaining_future = cursor.fetchone()[0]
print(f"Remaining future tasks: {remaining_future}")

# Show overdue tasks
cursor.execute("SELECT COUNT(*) FROM tasks WHERE next_run < ?", (now,))
overdue = cursor.fetchone()[0]
print(f"Overdue tasks: {overdue}")

conn.close()