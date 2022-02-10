import time
import amazon_sp_api as sp_api
import config as DATA


class AmazonSettings:
	def __init__(
		self,
		iam_arn: str = None,
		refresh_token: str = None,
		client_id: str = None,
		client_secret: str = None,
		aws_access_key: str = None,
		aws_secret_key: str = None,
		country: str = None,
		max_retry_limit: int = 5,
	) -> None:
		self.iam_arn = iam_arn or DATA.IAM_ARN
		self.refresh_token = refresh_token or DATA.REFRESH_TOKEN
		self.client_id = client_id or DATA.CLIENT_ID
		self.client_secret = client_secret or DATA.CLIENT_SECRET
		self.aws_access_key = aws_access_key or DATA.AWS_ACCESS_KEY
		self.aws_secret_key = aws_secret_key or DATA.AWS_SECRET_KEY
		self.country = country or DATA.COUNTRY_CODE
		self.max_retry_limit = max_retry_limit or DATA.MAX_RETRY_LIMIT


class AmazonRepository:
	def __init__(self, amazon_settings: AmazonSettings = None) -> None:
		self.amz_settings = amazon_settings or AmazonSettings()
		self.instance_params = dict(
			iam_arn=self.amz_settings.iam_arn,
			client_id=self.amz_settings.client_id,
			client_secret=self.amz_settings.client_secret,
			refresh_token=self.amz_settings.refresh_token,
			aws_access_key=self.amz_settings.aws_access_key,
			aws_secret_key=self.amz_settings.aws_secret_key,
			country_code=self.amz_settings.country,
		)

	# Helper Methods
	def return_as_list(self, input):
		if isinstance(input, list):
			return input
		else:
			return [input]

	def call_sp_api_method(self, sp_api_method, **kwargs):
		errors = {}
		max_retries = self.amz_settings.max_retry_limit

		for x in range(max_retries):
			try:
				response = sp_api_method(**kwargs)
				return response.json()
			except sp_api.SPAPIError as e:
				if e.error not in errors:
					errors[e.error] = e.error_description
				time.sleep(1)
				continue

		for error in errors:
			msg = f"Error: {error}\nError Description: {errors.get(error)}"

	# Feeds Section
	def get_feeds_instance(self):
		return sp_api.Feeds(**self.instance_params)
	
	# Finances Section
	def get_finances_instance(self):
		return sp_api.Finances(**self.instance_params)
	
	# FBAInventory Section
	def get_fba_inventory_instance(self):
		return sp_api.FBAInventory(**self.instance_params)

	# Orders Section
	def get_orders_instance(self):
		return sp_api.Orders(**self.instance_params)
	
	def get_orders(self, created_after):
		result = []
		orders = self.get_orders_instance()
		order_statuses = [
			"PendingAvailability",
			"Pending",
			"Unshipped",
			"PartiallyShipped",
			"Shipped",
			"InvoiceUnconfirmed",
			"Canceled",
			"Unfulfillable",
		]
		fulfillment_channels = ["FBA", "SellerFulfilled"]

		orders_payload = self.call_sp_api_method(
			sp_api_method=orders.get_orders,
			created_after=created_after,
			order_statuses=order_statuses,
			fulfillment_channels=fulfillment_channels,
			max_results=50,
		).get("payload")

		while True:
			result.extend(orders_payload.get("Orders"))
			next_token = orders_payload.get("NextToken")

			if not next_token:
				break

			orders_payload = self.call_sp_api_method(
				sp_api_method=orders.get_orders, created_after=created_after, next_token=next_token
			)
		
		return result

	# ProductFees Section
	def get_product_fees_instance(self):
		return sp_api.ProductFees(**self.instance_params)

	# CatalogItems or Products Section
	def get_catalog_items_instance(self):
		return sp_api.CatalogItems(**self.instance_params)

	# Pricing Section
	def get_pricing_instance(self):
		return sp_api.Pricing(**self.instance_params)
	
	# Reports Section
	def get_reports_instance(self):
		return sp_api.Reports(**self.instance_params)

	# Sellers Section
	def get_sellers_instance(self):
		return sp_api.Sellers(**self.instance_params)
