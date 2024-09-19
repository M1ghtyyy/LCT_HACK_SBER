import pandas as pd
import joblib
from prophet import Prophet

file_path = '5400-2024'
data = pd.read_excel(file_path)

data_cleaned = data[data['Сумма распределения'] != 0].copy()
data_cleaned = data_cleaned.drop(columns=['Класс ОС', 'ID основного средства', 'Счет главной книги'])
data_cleaned['Дата отражения в учетной системе'] = pd.to_datetime(data_cleaned['Дата отражения в учетной системе'])
data_cleaned['Дата отражения в учетной системе'] = data_cleaned['Дата отражения в учетной системе'].fillna(method='ffill')
data_cleaned['year_month'] = data_cleaned['Дата отражения в учетной системе'].dt.to_period('M').dt.to_timestamp()

buildings_to_predict = data_cleaned['Здание'].unique()

new_file_path = '5400-2023'
new_data = pd.read_excel(new_file_path)

new_data_cleaned = new_data[new_data['Сумма распределения'] != 0].copy()
new_data_cleaned = new_data_cleaned.drop(columns=['Класс ОС', 'ID основного средства', 'Счет главной книги'])
new_data_cleaned['Дата отражения в учетной системе'] = pd.to_datetime(new_data_cleaned['Дата отражения в учетной системе'])
new_data_cleaned['Дата отражения в учетной системе'] = new_data_cleaned['Дата отражения в учетной системе'].fillna(method='ffill')
new_data_cleaned['month'] = new_data_cleaned['Дата отражения в учетной системе'].dt.to_period('M')
new_monthly_data = new_data_cleaned.groupby(['Здание', 'month']).agg({'Сумма распределения': 'sum', 'Площадь': 'mean'}).reset_index()
new_monthly_data['month'] = new_monthly_data['month'].dt.to_timestamp()

models = {}
list_b = []
counter = 0

for building_id in new_monthly_data['Здание'].unique():
    building_data = new_monthly_data[new_monthly_data['Здание'] == building_id]
    building_data = building_data[['month', 'Сумма распределения','Площадь']] 
    building_data.columns = ['ds', 'y', 'Площадь'] 
    
    if building_data.dropna().shape[0] < 2:
        counter += 1
        list_b.append(building_id)
        continue

    model = Prophet(
        seasonality_mode='multiplicative', 
        seasonality_prior_scale=0.01,
        changepoint_prior_scale=0.01,
        yearly_seasonality=False,
        weekly_seasonality=False,  
        daily_seasonality=False,
    )
    model.add_seasonality(name='quarterly', period=60.5, fourier_order=3)

    model.fit(building_data)
    models[building_id] = model

print(f'Пропущенные здания: {counter}')
print(f'Идентификаторы пропущенных зданий: {list_b}')

future_months = pd.DataFrame({'ds': pd.date_range(start='2024-01-01', periods=5, freq='MS')})

predictions = {}

for building_id in buildings_to_predict:
    if building_id in models:
        model = models[building_id]
        future = future_months.copy()
        average_area = data_cleaned[data_cleaned['Здание'] == building_id]['Площадь'].mean()
        future['Площадь'] = average_area
        forecast = model.predict(future)
        forecast['Здание'] = building_id
        predictions[building_id] = forecast[['ds', 'yhat', 'Здание']]


all_predictions = pd.concat(predictions.values(), axis=0).reset_index(drop=True)

print(all_predictions)

joblib.dump(models, 'test_model.pkl')

all_predictions['year_month'] = all_predictions['ds'].dt.to_period('M').dt.to_timestamp()


monthly_sum = all_predictions.groupby('year_month').agg({'yhat': 'sum'}).reset_index()
monthly_sum.rename(columns={'yhat': 'Прогнозируемая сумма'}, inplace=True)


data_cleaned['year_month'] = pd.to_datetime(data_cleaned['year_month'])


actual_monthly_sum = data_cleaned.groupby('year_month')['Сумма распределения'].sum().reset_index()

monthly_sum['year_month'] = pd.to_datetime(monthly_sum['year_month'])
actual_monthly_sum['year_month'] = pd.to_datetime(actual_monthly_sum['year_month'])

merged_sums = pd.merge(monthly_sum, actual_monthly_sum, on='year_month', how='inner')

merged_sums['absolute_difference'] = abs(merged_sums['Прогнозируемая сумма'] - merged_sums['Сумма распределения'])

print(merged_sums)
