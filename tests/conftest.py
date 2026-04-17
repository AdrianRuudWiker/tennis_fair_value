"""
conftest.py
Adds src/ to sys.path so tests can import markov, match, etc. directly.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
