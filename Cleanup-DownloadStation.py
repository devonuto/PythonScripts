import requests
import time
import json

class SynologyDownloadStation:
    def __init__(self, nas_ip, user_id, password):
        self.nas_ip = nas_ip
        self.user_id = user_id
        self.password = password
        self.session_id = None        
        self.two_weeks_ago = time.time() - 2 * 7 * 24 * 60 * 60  # Two weeks in seconds

    def log_into_download_station(self):
        print("Logging into Download Station")
        url = f"http://{self.nas_ip}/webapi/auth.cgi?api=SYNO.API.Auth&version=3&method=login&account={self.user_id}&passwd={self.password}&session=DownloadStation&format=cookie"
        response = requests.get(url)
        data = response.json()
        if data.get('success'):
            self.session_id = data['data']['sid']
        else:
            raise Exception("Failed to log in")

    def log_out_of_download_station(self):
        if self.session_id:
            print("Logging out")
            url = f"http://{self.nas_ip}/webapi/auth.cgi?api=SYNO.API.Auth&version=1&method=logout&session=DownloadStation"
            requests.get(url, cookies={'id': self.session_id})
            self.session_id = None

    def get_download_tasks(self):
        print("Getting download tasks")
        url = f"http://{self.nas_ip}/webapi/DownloadStation/task.cgi?api=SYNO.DownloadStation.Task&version=1&method=list&additional=detail,file"
        response = requests.get(url, cookies={'id': self.session_id})
        data = response.json()
        if data.get('success'):
            return data['data']['tasks']
        else:
            return []

    def delete_download_task(self, task_id):
        url = f"http://{self.nas_ip}/webapi/DownloadStation/task.cgi?api=SYNO.DownloadStation.Task&version=1&method=delete&id={task_id}"
        response = requests.get(url, cookies={'id': self.session_id})
        data = response.json()
        return data.get('success', False)

    def clean_up_download_tasks(self):
        tasks = self.get_download_tasks()
        tasks_to_keep = []
        for task in tasks:
            create_time = task['additional']['detail'].get('create_time')
            print(f"Created: {create_time}. \"{task['title']}\", Status: {task['status']}")
            if task['status'] == 'error' or (create_time is not None and create_time < self.two_weeks_ago):
                if self.delete_download_task(task['id']):
                    print(f"Deleted task ID: {task['id']} for \"{task['title']}\"")
                else:
                    raise Exception(f"Failed to delete task ID: {task['id']}")
            else:
                tasks_to_keep.append(task)
        return tasks_to_keep

if __name__ == "__main__":
    nas_ip = "127.0.0.1:5916"
    user_id = "Download_Station"
    password = "tCGbA90WB!S9"

    ds = SynologyDownloadStation(nas_ip, user_id, password)
    try:
        ds.log_into_download_station()
        ds.clean_up_download_tasks()
    finally:
        ds.log_out_of_download_station()
