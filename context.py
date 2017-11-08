"""Dirty work so other test modules can import rest.* modules easily."""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rest import tokens, github, util
