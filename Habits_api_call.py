
#%% Imports

from datetime import datetime,timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText  # Import MIMEText
import json
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
import pandas as pd
import requests
import seaborn as sns
import smtplib
from sqlalchemy import  create_engine, Integer, String, Float
import time

#%% NB THIS SECTION (AND THE CREDENTIALS JSON FILE) SHOULD BE THE ONLY THINGS YOU NEED TO CHANGE TO RUN THIS NOW.


credential_file_dir = "C:\Rob_python_scripts\habits"

# Load the credentials file
with open(credential_file_dir+"\credentials.json", "r") as file:
    credentials = json.load(file)


#%%
# Access values
#Habitica API >>
habitica_api_user = credentials.get("habitica_api_user")
habitica_api_key = credentials.get("habitica_api_key")
#SSMS Server name>>
ssms_db_server = credentials.get("server")
#email address and associated App password to send emails from
from_email_address = credentials.get("from_email_address")
from_email_address_app_password = credentials.get("from_email_app_password")
#email address to send the email and pdf to
email_address_to_send_email_to = credentials.get("to_email_address")


#%% API endpoint and app name (needed to run API)

habitica_json_export_api = "https://habitica.com/export/userdata.json"
downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')

#%% credentials of datase I want to store API info in 

# Database credentials to upload to
server = ssms_db_server
database = 'habits'
user = '' #leave blank for widows authentication
password = '' #leave blank for widows authentication
driver = 'ODBC Driver 17 for SQL Server'

#%%  functions

def combine_list_of_strings(list_of_strings :list):
    """ This function is used to insert a list of dates into a string, 
        in order to be inserted into an sql script"""
    final_string = ""
    for x in list_of_strings:
        final_string = final_string + ',' + x
        #print(final_string)
    final_string = final_string[1:]
    return final_string


def last_seven_days(date_in_yyyymmdd:str):
    """gives list of yyyymmdd strings of last 7 days, for graph visualisation"""
    end_date = datetime.strptime(date_in_yyyymmdd, "%Y%m%d").date()
    start_date = end_date - timedelta(days=6)                                  #this is 6 as it is inclusive
    date_list = []
    
    # Loop through the range of dates and append to the list
    while start_date <= end_date:
        date_list.append(start_date.strftime("%Y%m%d"))
        start_date += timedelta(days=1)
    return date_list 


def ssms_database_connection(server:str, database:str, username:str,password:str, driver:str):
    """Takes: server, database, username, password and driver as strings to form an SSMS connection. 
        You can leave username and password asblank strings ('') to use windows authentication."""
    
    conn_str = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver}"
    engine = create_engine(conn_str)
    return engine

def today():
    a = datetime.now().strftime("%Y%m%d")
    return a

def today_datetime():
    b = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
    return b

#%% Setup credentials for API call

# Define the API URL
url = "https://habitica.com/export/userdata.json"

# Set up the request headers for authentication
headers = {
    "x-api-user": habitica_api_user,
    "x-api-key": habitica_api_key
}

#%% Make Habitica API call


print("Process started at: {}".format( today_datetime() ) )

response = requests.get(url, headers=headers)
today_yyyymmdd = today()

#df setup
df_headings = ["date_yyyymmdd","habit","completed"]
df_list = []


# Check if the request was successful
if response.status_code == 200:
    userdata = response.json()  # Parse response once

    for daily_task in userdata["tasks"]["dailys"]:
        if not daily_task["checklist"]:                                        #if checklist is empty
            habit = daily_task["text"]                                         #get text I.E Name of task
            completed_flag = daily_task["completed"]                           #get completion
            df_list.append([today_yyyymmdd, habit, completed_flag])
        else:
            for checklist_item in daily_task["checklist"]:                     #otherwise,get checklist item
                habit = checklist_item["text"]                                  #get name of checklist item
                completed_flag = checklist_item["completed"]                   #get completion of checklist item
                df_list.append([today_yyyymmdd, habit, completed_flag])
            
#Add data to DataFrame and sleep (required by api rules)
df =pd.DataFrame(df_list,columns=df_headings)
time.sleep(30)
print("-> API data retrieved at {}".format(today_datetime()))


#%% RUN SQL SCRIPT TO FIND LATEST UPDATE DATE


#Connect to db
engine = ssms_database_connection(server,database,user,password,driver)

#run SQL query to work out latest date, to see if update is required
sql_query = """
SELECT MAX(date_yyyymmdd) from [dbo].[{}];
""".format(database)

# Execute the SQL query and load the results into a Pandas DataFrame, set max date to variable
max_db_date_df = pd.read_sql_query(sql_query, engine)
max_db_date = max_db_date_df.iloc[0, 0]    # Extract first row, first column 
#max_db_date = 20250215   # use this with yesterdays date if there is 0 records in table (it a growing table, so it shouldnt be a problem after day 11)                            

# Display the results stored in variable
print("-> Max date ({}) was retrieved from SSMS database at {}.".format(max_db_date,today_datetime()) )


#%% evaluate whether db needs to be update today and if it does add data to SSMS database.


if int(today_yyyymmdd) > int(max_db_date):
    datetime_var1 = today_datetime()
    print("-> Copying dataframe into SSMS database. The upload started at {}.\n".format(datetime_var1) )
    
    df.to_sql(database,con=engine,if_exists='append',index=False) #change to append
    
    datetime_var2 = today_datetime()
    print("✅ Habit records finished uploading at {}.".format(datetime_var2) )
else:
    print("❌ No upload performed. There was already uploaded data for {}".format(max_db_date)
          + " in SSMS database, so nothing was updated."
          + " Delete data for {} if you want to reupload.".format(max_db_date) )
    
print("-> Habits SSMS table evaluated and updated (if it was required).")


#%% This creates/appends a table that shows the average completion rate for each habit for the last week


#gets list of last 7 days
list_of_yyyymmdd_for_last_7_days = last_seven_days(today_yyyymmdd)

#get rolling average for completion rate for last weeks data
#need to append this to a table
sql_query2 = """
WITH avg_by_habit_last_seven_days AS (
	SELECT 
		[date_yyyymmdd], [habit], CAST([completed] AS FLOAT) AS completed
	FROM 
		[dbo].[{}] 
	WHERE 
		CAST([date_yyyymmdd] AS DATE) BETWEEN DATEADD(DAY, -6, CAST([date_yyyymmdd] AS DATE)) AND CAST([date_yyyymmdd] AS DATE) /*gets relevant dates*/
)
SELECT 
    max([date_yyyymmdd]) as date_yyyymmdd, /*adds back in todays date*/
    [habit],
	AVG(CAST([completed] AS FLOAT)) AS avg_weekly_completion_rate /*averages relevant dates*/
FROM 
	avg_by_habit_last_seven_days 
GROUP BY 
    [habit]
""".format(database)

habits_for_last_week_data= pd.read_sql_query(sql_query2, engine)

# Adds the results of SQL query 2 to a DF. The section below may show [-1] even when it succesfully uploads.
habits_for_last_week_data.to_sql('average_habit_completion'
                                 ,con=engine
                                 ,if_exists='append'
                                 ,index=False                                
                                 )
print("-> Average completion rate for each habit in the last 7 days has been calculated and"
      + " added into 'Average_habit_completion' SSMS table.")


#%% create df of longest streak per habit


#do this last - seems v complex: see site here: https://stackoverflow.com/questions/75816823/get-most-recent-streak-consecutive-days-for-given-event-and-time-zone

#%%  format query string with last weeks dates 


# SQL query to fetch data
sql_query3 = """
select *
from [dbo].[average_habit_completion] 
where date_yyyymmdd in ({})
""".format(str(combine_list_of_strings(list_of_yyyymmdd_for_last_7_days)))

rolling_ave_habit_data = pd.read_sql_query(sql_query3, engine)

# Ensure date is in datetime format
rolling_ave_habit_data["date_yyyymmdd"] = pd.to_datetime(
    rolling_ave_habit_data["date_yyyymmdd"], format="%Y%m%d"
)

# Convert avg_weekly_completion_rate to percentage
rolling_ave_habit_data["avg_weekly_completion_rate"] *= 100  

# Create a figure for the plots
num_habits = rolling_ave_habit_data['habit'].nunique()  # Get the number of unique habits
fig, axs = plt.subplots(nrows=num_habits, ncols=1, figsize=(12, 4 * num_habits), sharex=True)

# Plot each habit in its own subplot
for ax, (habit, data) in zip(axs, rolling_ave_habit_data.groupby('habit')):
    sns.lineplot(
        data=data,
        x="date_yyyymmdd",
        y="avg_weekly_completion_rate",
        ax=ax,
        marker="o"  # Add circular markers
    )
    
    # Format y-axis as percentage and set limit to 100%
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.set_ylim(0, 100)
    ax.set_title(habit)  # Set the title to the habit name

    # Format x-axis labels as YYYYMMDD & rotate for readability
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y%m%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.tick_params(axis="x", rotation=45)  # Rotate x-axis labels

    # Add callouts for each point
    for index, row in data.iterrows():
        ax.annotate(f"{row['avg_weekly_completion_rate']:.1f}%", 
                    (row["date_yyyymmdd"], row["avg_weekly_completion_rate"]),
                    textcoords="offset points",  # How to position the text
                    xytext=(0, -10),  # Distance from the point
                    ha='center', 
                    fontsize=9)

# Create a legend below all plots
handles, labels = axs[0].get_legend_handles_labels()  # Get handles and labels from the first ax
fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.05), ncol=3)

plt.tight_layout(rect=[0, 0.1, 1, 1])  # Adjust layout to fit the legend

plt.subplots_adjust(hspace=0.5)  # Increase vertical space (hspace) between graphs

# Save the plot as a PDF
plt.savefig(downloads_folder+"\habit_completion_rates.pdf", format="pdf", bbox_inches="tight", pad_inches=1)

#plt.show() #COMMENTED OUT TO ALLOW THIS TIO RUN IN BAT FILE/TASK SCHEDULER WITHOUT HANGING INDEFINITELY

print("-> PDF attachment has been generated for the rolling 7 day average of habits."
      + " It was completed at {}".format(today_datetime()))


#%% Now send email to myself daily to get graph (attachemnt or embed, not sure yet)


# Email credentials
email_address = from_email_address
email_password = from_email_address_app_password   #generate app pw here: "https://myaccount.google.com/apppasswords?pli=1&rapt=AEjHL4PIurSmG468mXmN_7-eeLmWllnM6jBPTiSklVj4Ys7jKm0_W-8hcw8xIVYtnxfXEiHh1VsBfpZkxh65Tdmwhzoet8VR9fHYK-hmO1XWMKvdpwtbptY"

#This is an app password generated in gmail. 
#Text based Explanation found here: "https://mailmeteor.com/blog/gmail-smtp-settings#how-to-use-the-gmail-smtp-settings" and 
#Youtube (with key link in desc) found here: "https://www.youtube.com/watch?v=sKJ_Mzc7hM8" 

# Email content
to_address = email_address_to_send_email_to
subject = 'Weekly Habit Completion Rates Graph' #add todays date
body = 'Hi,\n\nPlease find attached my latest habit completion rates for the last week.\n\nWarmest regards,\nRob.'

# Path to the PDF file
pdf_file_path = downloads_folder+"\habit_completion_rates.pdf"

# Create a multipart email
msg = MIMEMultipart()
msg['From'] = email_address
msg['To'] = to_address
msg['Subject'] = subject
msg.attach(MIMEText(body, 'plain'))

# Attach the PDF file
with open(pdf_file_path, 'rb') as attachment:
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(pdf_file_path)}')
    msg.attach(part)

# Send the email
try:
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(email_address, email_password)
        server.send_message(msg)
    print("✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Failed to send email: {e}")

print("Process finished at: {}".format(today_datetime()))

