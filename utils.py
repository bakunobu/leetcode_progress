
import re
import datetime as dt
import doctest
import datetime as dt

def hand_input() -> str:
    """
    Function gets user input in format (L) or (L YYYY-mm-dd) 
    where L is question difficulty (E, M, H) and YYYY-mm-dd is the date (optional).

    Returns:
        str: The input in format 'L' or 'L YYYY-mm-dd' if date is valid and not in the future.

    Raises:
        ValueError: If date format is incorrect or date is in the future.
    """
    while True:
        rec = input('Enter task difficulty (E, M, H) and date (YYYY-mm-dd, optionally): ').upper().strip()
        
        parts = rec.split()
        difficulty = parts[0]
        
        if difficulty not in 'EHM':
            print('Wrong input. Try again.')
            continue
            
        if len(parts) == 1:
            return rec
        
        if len(parts) == 2:
            date_str = parts[1]
            try:
                # Convert the input date string to a datetime object
                input_date = dt.datetime.strptime(date_str, '%Y-%m-%d').date()
                today = dt.date.today()
                
                if input_date <= today:
                    return rec
                else:
                    print("Can't add future date")
            except ValueError:
                print('Wrong input. Try again.')
        else:
            # Handles cases like "E 2023-10-05 extra" or "E M"
            print('Wrong input. Try again.')


