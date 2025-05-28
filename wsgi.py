import sys
import os


# Dodaj katalog aplikacji do ścieżki systemowej
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

from run import app as application

# Opcjonalnie dla debugowania
if __name__ == "__main__":
    application.run()