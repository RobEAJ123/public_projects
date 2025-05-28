# -*- coding: utf-8 -*-
"""
@author: ashto
"""
#%% Import Libraries


import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
#import seaborn as sns
from scipy.stats import zscore
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error


#%% Functions


def remove_outliers_zscore(df, column, threshold=3):
    z_scores = zscore(df[column])
    return df[abs(z_scores) < threshold]


#%% Load the Data and drop nulls

directory = "C:/Users/ashto/Downloads" 
df = pd.read_csv(directory + '/CoStar height analysis.csv')
df = df[df["heightsrc"] == "Mixed_non_ai"].copy() #remove ai generated estimates from CoStar buildings data

#remove nulls from key from key cols
df = df[["height","Number Of Stories","RAJ_URN","heightsrc"]]
df['Number Of Stories'] = df['Number Of Stories'].replace(r'^\s*#N/A\s*$', np.nan, regex=True) #convert dodgy #NA val;ues in excel to actaul NaNs
df['Number Of Stories'] = pd.to_numeric(df['Number Of Stories'], errors='coerce')
df.dropna(subset=['Number Of Stories', 'height'], axis=0, inplace=True)

#remove outliers from columns of interest
df = remove_outliers_zscore(df, 'height')
df = remove_outliers_zscore(df, 'Number Of Stories')


#%% EDA


#print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
#print(df.head())
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print(df.describe())
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print(df.info())
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

#sns.scatterplot(x='Number Of Stories', y='height', data=df)
#plt.show()


#%% Preprocess the Data


X = df[['Number Of Stories']] 
y = df['height'] 


#%%  Train/Test Split


X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


#%% Create and fit model (force 0,0 intercept as buildings with 0 floors should be 0m high)


model = LinearRegression(fit_intercept=False)
model.fit(X_train, y_train)


#%% Make Predictions


y_pred = model.predict(X_test)


#%% Evaluate the Model


slope = model.coef_[0]
intercept = model.intercept_
r2 = r2_score(y_test, y_pred)

print("Intercept:", model.intercept_)
print("Coefficient:", model.coef_[0])
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
print("R² Score:", r2_score(y_test, y_pred))
print("MAE:", mean_absolute_error(y_test, y_pred))
print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")


#%% Visualize the Results


plt.scatter(X_test, y_test, label='Actual')
plt.plot(X_test, y_pred, color='red', label='Predicted')

# Add formula and R² to the plot
formula_text = f'y = {slope:.2f}x + {intercept:.2f}\n$R^2$ = {r2:.2f}'
plt.text(
    0.95, 0.05, formula_text,
    fontsize=10, color='black',
    ha='right', va='bottom',
    transform=plt.gca().transAxes
)

plt.legend()
plt.xlabel('Number Of Stories in building (CoStar)')
plt.ylabel('Height (m) for "Mixed non-ai labelled buildings"')
plt.title('Number of Storeys Vs Building Height')
plt.show()

