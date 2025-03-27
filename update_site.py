import httpx
import json
import re
import datetime
from pathlib import Path



class DogeAPIMonitor():
    def __init__(self, initial_data=None):
        if initial_data is None:
            self.db = {
                "data": {
                    "grants": {},
                    "contracts": {},
                    "leases": {},
                    "payments": {}
                },
                "page_offsets": {
                    "grants": 0,
                    "contracts": 0,
                    "leases": 0,
                    "payments": 0
                }
            }
        else:
            with open(initial_data, "r", encoding="utf-8") as file:
                self.db = json.load(file)


    def save_data(self, fname):
        with open(fname, "w", encoding="utf-8") as file:
            json.dump(self.db, file)
        
    def get_data(self, category):
        assert category in self.db["data"].keys()
        finished = False
        while not finished:
            print(f"Processing page {max(1, self.db['page_offsets'][category])} of {category}", end='\r', flush=True)
            params = {
                "sort_by": "date",
                "sort_order": "asc",
                "page": max(1, self.db["page_offsets"][category]),
                "per_page": 500
            }
            url = f"https://api.doge.gov/savings/{category}"
            if category in ("payments", ):
                params["sort_by"] = "post_date"
                url = f"https://api.doge.gov/{category}"
            r = httpx.get(url, params=params)
            if r.status_code == 200 and r.json().get("success"):
                if len(r.json().get("result", {}).get(category, [])) == 0:
                    finished = True
                for result in r.json().get("result", {}).get(category, []):
                    key = hash(str({key: val for key, val in sorted(result.items(), key = lambda x: x[0])}))
                    self.db["data"][category][key] = result
            if finished:
                print(f"Processing page {max(1, self.db['page_offsets'][category])} of {category}")
            self.db["page_offsets"][category] += 1


    def update(self):
        for category in self.db["data"].keys():
            self.get_data(category)

    @property
    def categories(self):
        return sorted(self.db["data"].keys())
    
    @property
    def agencies(self):
        return sorted(set().union(*[{item.get("agency", "") for item in self.db["data"][category].values()} for category in self.db["data"].keys()]))


    @property
    def structure(self):
        return {category: set().union(*[{key for key in value.keys()} for value in self.db["data"][category].values()]) for category in self.db["data"].keys()}



# Function to generate the markdown table
def generate_markdown_table(data):
    if not data:
        return ""

    # Extract the headers from the first dictionary
    headers = data[0].keys()

    # Create the header row
    header_row = "| " + " | ".join(headers) + " |"

    # Create the separator row
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"

    # Create the data rows
    data_rows = []
    for row in data:
        data_row = "| " + " | ".join(str(value) for value in row.values()) + " |"
        data_rows.append(data_row)

    # Combine all rows into a single string
    table = "\n".join([header_row, separator_row] + data_rows)

    return table


def matches_regex(pattern, string):
    if re.match(pattern, string):
        return True
    else:
        return False

def format_dollar_amount(amount):
    return "${:,.2f}".format(amount)


if __name__ == "__main__":
    if Path("db.json").is_file():
        api_monitor = DogeAPIMonitor("db.json")
    else:
        api_monitor = DogeAPIMonitor()
    api_monitor.update()

    columns_dollar = ("savings", "value", "amount")

    date_sorting = {
        "grants": "date",
        "contracts": "deleted_date",
        "leases": "date",
        "payments": "post_date"
    }

    searches = {
        "NASA": "NASA|National Aeronautics and Space Administration"
    }
    text = ""
    for title, agency in searches.items():
        text += f"# {title}\n"
        for category in api_monitor.categories:
            text += f"## {category}\n\n"
            columns = api_monitor.structure.get(category, {})
            data = [{column: (entry.get(column, "") or "") for column in columns} for entry in api_monitor.db["data"][category].values() if matches_regex(agency, entry.get("agency"))]
            for i, entry in enumerate(data):
                for key in entry.keys():
                    data[i][key] = data[i][key].replace("\n", " ").replace("\r", " ")
                    if key in columns_dollar:
                        try:
                            data[i][key] = format_dollar_amount(data[i][key])
                        except:
                            pass
            date_key = date_sorting.get(category)
            if date_key:
                data = sorted(data, key=lambda x: datetime.datetime.strptime(x[date_key], "%m/%d/%Y"), reverse=True)
            text += generate_markdown_table(data)
            text += "\n\n"
        text += "\n"
    
    with open("docs/index.md", "w") as file:
        file.write(text)
    api_monitor.save_data("db.json")
