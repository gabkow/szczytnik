import time
import sys

print("Worker uruchomiony i gotowy do pracy...", flush=True)

while True:
    # Symulacja pętli sprawdzającej bazę danych
    print("Sprawdzam nowe zadania w bazie danych...", flush=True)
    
    # Tu w przyszłości pojawi się logika sprawdzania tabeli 'jobs'
    
    time.sleep(15) # Sprawdzaj co 15 sekund