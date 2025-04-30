from datetime import datetime, timedelta

def get_date_ranges(last_run_date=None):
    """Returns (start_date, end_date) for scraping as strings"""
    end_date = datetime.now()
    
    if last_run_date:
        # Convert string to datetime if needed
        if isinstance(last_run_date, str):
            last_run_date = datetime.strptime(last_run_date, '%Y-%m-%d')
        start_date = last_run_date
    else:
        # First run (1 year lookback)
        start_date = end_date - timedelta(days=365)
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')