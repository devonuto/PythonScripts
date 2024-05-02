import datetime
import re

def extract_unique_days(file_path):
    unique_dates = set()  # Use a set to store unique dates
    date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')  # Regex to match YYYY-MM-DD format

    with open(file_path, 'r') as file:
        for line in file:
            file_name = line.strip().split('\\')[-1]  # Get the file name
            # Search for date pattern in the file name
            match = date_pattern.search(file_name)
            if match:
                date_part = match.group(0)  # Extract the date string
                try:
                    date_obj = datetime.datetime.strptime(date_part, '%Y-%m-%d')
                    # Format date as 'd MMM yyyy'
                    formatted_date = date_obj.strftime('%d %b %Y').lstrip('0')
                    unique_dates.add(formatted_date)
                except ValueError as e:
                    print(f"Skipping file due to error parsing date: {file_name}, Error: {str(e)}")
            else:
                print(f"No valid date found in file name: {file_name}")

    return list(unique_dates)


# Example usage
file_path = 'D:\\My Photos\\corrupted_photos.txt'
dates = extract_unique_days(file_path)
print(dates)
