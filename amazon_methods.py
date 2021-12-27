import time
import config
import amazon_sp_api as sp_api


def return_as_list(input):
	if isinstance(input, list):
		return input
	else:
		return [input]

def call_sp_api_method(sp_api_method, **kwargs):
	max_retries = config.MAX_RETRY_LIMIT

	for x in range(max_retries):
		try:
			response = sp_api_method(**kwargs)
			return response
		except Exception:
			time.sleep(1)
			continue
	
	print("Max retry limit reached.")

def get_orders_instance():
	orders = sp_api.Orders(
		iam_arn=config.IAM_ARN,
		client_id=config.CLIENT_ID,
		client_secret=config.CLIENT_SECRET,
		refresh_token=config.REFRESH_TOKEN,
		aws_access_key=config.AWS_ACCESS_KEY,
		aws_secret_key=config.AWS_SECRET_KEY,
		selling_region=config.SELLING_REGION,
		country_code=config.COUNTRY_CODE,
	)

	return orders

def get_orders(created_after):
	try:
		orders = get_orders_instance()
		orders_response = call_sp_api_method(
			sp_api_method=orders.get_orders,
			created_after=created_after,
			max_results=50,
		)
		
		print(orders_response.text)

	except Exception as e:
		print(e)
	
def get_order_items(order_id):
	try:
		orders = get_orders_instance()
		order_items_response = call_sp_api_method(
			sp_api_method=orders.get_order_items,
			order_id=order_id,
		)
		
		print(order_items_response.text)

	except Exception as e:
		print(e)








	


	
