import boto3
from requests import request
from aws_sig_v4 import AWSSigV4
from requests.exceptions import HTTPError


__all__ = [
	"SPAPIError",
	"Feeds",
	"Finances",
	"FBAInventory",
	"Orders",
	"ProductFees",
	"CatalogItems",
	"Pricing",
	"Reports",
	"Sellers",
]

# https://github.com/amzn/selling-partner-api-docs/blob/main/guides/en-US/developer-guide/SellingPartnerApiDeveloperGuide.md#selling-partner-api-endpoints
MARKETPLACES = {
	"North America": {
		"CA": "A2EUQ1WTGCTBG2",
		"US": "ATVPDKIKX0DER",
		"MX": "A1AM78C64UM0Y8",
		"BR": "A2Q3Y263D00KWC",
		"AWS Region": "us-east-1",
		"Endpoint": "https://sellingpartnerapi-na.amazon.com",
	},
	"Europe": {
		"ES": "A1RKKUPIHCS9HS",
		"GB": "A1F83G8C2ARO7P",
		"FR": "A13V1IB3VIYZZH",
		"NL": "A1805IZSGTT6HS",
		"DE": "A1PA6795UKMFR9",
		"IT": "APJ6JRA9NG5V4",
		"SE": "A2NODRKZP88ZB9",
		"PL": "A1C3SOZRARQ6R3",
		"EG": "ARBP9OOSHTCHU",
		"TR": "A33AVAJ2PDY3EV",
		"SA": "A17E79C6D8DWNP",
		"AE": "A2VIGQ35RCS4UG",
		"IN": "A21TJRUUN4KGV",
		"AWS Region": "eu-west-1",
		"Endpoint": "https://sellingpartnerapi-eu.amazon.com",
	},
	"Far East": {
		"SG": "A19VAU5U5O7RUS",
		"AU": "A39IBJ37TRP1C6",
		"JP": "A1VC38T7YXB528",
		"AWS Region": "us-west-2",
		"Endpoint": "https://sellingpartnerapi-fe.amazon.com",
	},
}

class SPAPIError(Exception):
	"""
	Main SP-API Exception class
	"""

	# Allows quick access to the response object.
	# Do not rely on this attribute, always check if its not None.
	response = None

class SPAPI(object):
	""" Base Amazon SP-API class """

	# https://github.com/amzn/selling-partner-api-docs/blob/main/guides/en-US/developer-guide/SellingPartnerApiDeveloperGuide.md#connecting-to-the-selling-partner-api
	AUTH_URL = "https://api.amazon.com/auth/o2/token"

	# https://github.com/amzn/selling-partner-api-docs/blob/main/guides/en-US/developer-guide/SellingPartnerApiDeveloperGuide.md#step-1-request-a-login-with-amazon-access-token
	SCOPE = {"notifications": "sellingpartnerapi::notifications", "migration": "sellingpartnerapi::migration"}

	BASE_URI = "/"

	def __init__(self, iam_arn:str, client_id:str, client_secret:str, refresh_token:str, aws_access_key:str, aws_secret_key:str, selling_region:str="North America", country_code:str="US") -> None:
		self.iam_arn = iam_arn
		self.client_id = client_id
		self.client_secret = client_secret
		self.refresh_token = refresh_token
		self.aws_access_key = aws_access_key
		self.aws_secret_key = aws_secret_key
		self.selling_region = selling_region
		self.country_code = country_code
		self.region, self.endpoint, self.marketplace_id = Util.get_marketplace_data(selling_region, country_code)
	
	def get_access_token(self, grant_type:str="refresh_token") -> str:
		data = {
			"grant_type": grant_type,
			"client_id": self.client_id,
			"client_secret": self.client_secret
		}

		if grant_type == "client_credentials":
			data["scope"] = self.SCOPE.get("notifications")
		else:
			data["refresh_token"] = self.refresh_token

		response = request(method="POST", url=self.AUTH_URL, data=data)
		result = response.json()

		if response.status_code == 200:
			return result.get("access_token")
		
		raise SPAPIError(f"{result.get('error_description')}")

	def get_auth(self) -> AWSSigV4:
		client = boto3.client(
			"sts",
			aws_access_key_id=self.aws_access_key,
			aws_secret_access_key=self.aws_secret_key,
			region_name=self.region
		)

		response = client.assume_role(
			RoleArn=self.iam_arn,
			RoleSessionName="SellingPartnerAPI"
		)

		credentials = response["Credentials"]
		access_key_id = credentials["AccessKeyId"]
		secret_access_key = credentials["SecretAccessKey"]
		session_token = credentials["SessionToken"]

		return AWSSigV4(
			service="execute-api", 
			aws_access_key_id=access_key_id, 
			aws_secret_access_key=secret_access_key, 
			aws_session_token=session_token, 
			region=self.region
		)

	def get_headers(self) -> dict:
		return {"x-amz-access-token": self.get_access_token()}

	def make_request(self, method:str="GET", append_to_base_uri:str="", params:dict|None=None, data:dict|None=None) -> object:
		if isinstance(params, dict):
			params = Util.remove_empty(params)
		if isinstance(data, dict):
			data = Util.remove_empty(data)

		url = self.endpoint + self.BASE_URI + append_to_base_uri

		try:
			response = request(method=method, url=url, params=params, data=data, headers=self.get_headers(), auth=self.get_auth())
			return response
		except HTTPError as e:
			error = SPAPIError(str(e))
			error.response = e.response
			raise error
		
	def list_to_dict(self, key:str, values:list, data:dict) -> None:
		if values and isinstance(values, list):
			for idx in range(len(values)):
				data[f"{key}[{idx}]"] = values[idx]

class Feeds(SPAPI):
	pass

class Finances(SPAPI):
	""" Amazon Finances API """

	BASE_URI = "/finances/v0/"

	def list_financial_event_groups(
		self,
		max_results:int|None=None,
		started_before:str|None=None,
		started_after:str|None=None,
		next_token:str|None=None, 
	) -> object:
		""" Returns financial event groups for a given date range. """
		append_to_base_uri = "financialEventGroups"
		data = dict(
			MaxResultsPerPage=max_results,
			FinancialEventGroupStartedBefore=started_before,
			FinancialEventGroupStartedAfter=started_after,
			NextToken=next_token
		)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

	def list_financial_events_by_group_id(
		self,
		group_id:str,
		max_results:int|None=None,
		next_token:str|None=None
	) -> object:
		""" Returns all financial events for the specified financial event group. """
		append_to_base_uri = f"financialEventGroups/{group_id}/financialEvents"
		data = dict(
			MaxResultsPerPage=max_results,
			NextToken=next_token
		)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

	def list_financial_events_by_order_id(
		self,
		order_id:str,
		max_results:int|None=None,
		next_token:str|None=None
	) -> object:
		""" Returns all financial events for the specified order. """
		append_to_base_uri = f"orders/{order_id}/financialEvents"
		data = dict(
			MaxResultsPerPage=max_results,
			NextToken=next_token
		)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

	def list_financial_events(
		self,
		max_results:int|None=None,
		posted_after:str|None=None,
		posted_before:str|None=None,
		next_token:str|None=None, 
	) -> object:
		""" Returns financial events for the specified data range. """
		append_to_base_uri = f"financialEvents"
		data = dict(
			MaxResultsPerPage=max_results,
			PostedAfter=posted_after,
			PostedBefore=posted_before,
			NextToken=next_token
		)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

class FBAInventory(SPAPI):
	""" Amazon FBAInventory API """

	BASE_URI = "/fba/inventory/v1/summaries"

	def get_inventory_summaries(
		self, 
		granularity_id:str,
		details:bool|None=None,
		start_date_time:str|None=None,
		seller_skus:list|None=None,
		next_token:str|None=None,
		marketplace_ids:list|None=None,
	) -> object:
		""" Returns a list of inventory summaries. The summaries returned depend on the presence or absence of the startDateTime and sellerSkus parameters:

			> All inventory summaries with available details are returned when the startDateTime and sellerSkus parameters are omitted.
			> When startDateTime is provided, the operation returns inventory summaries that have had changes after the date and time specified. The sellerSkus parameter is ignored.
			> When the sellerSkus parameter is provided, the operation returns inventory summaries for only the specified sellerSkus. 
		"""
		data = dict(
			granularityType="Marketplace",
			granularityId=granularity_id,
			details=details,
			startDateTime=start_date_time,
			nextToken=next_token,
		)

		self.list_to_dict("sellerSkus", seller_skus, data)
		self.list_to_dict("marketplaceIds", marketplace_ids, data)

		if not marketplace_ids:
			marketplace_ids = [self.marketplace_id]
			data["MarketplaceIds"] = marketplace_ids

		return self.make_request(params=data)

class Orders(SPAPI):
	""" Amazon Orders API """

	BASE_URI = "/orders/v0/orders"

	def get_orders(
		self,
		created_after:str,
		created_before:str|None=None,
		last_updated_after:str|None=None,
		last_updated_before:str|None=None,
		order_statuses:list=[],
		marketplace_ids:list|None=None,
		fulfillment_channels:list=[],
		payment_methods:object=[],
		buyer_email:str|None=None,
		seller_order_id:str|None=None,
		max_results:int=100,
		easyship_shipment_statuses:list|None=None,
		next_token:str|None=None,
		amazon_order_ids:list|None=None,
		actual_fulfillment_supply_source_id:str|None=None,
		is_ispu:bool=False,
		store_chain_store_id:str|None=None
	) -> object:
		""" Returns orders created or updated during the time frame indicated by the specified parameters. You can also apply a range of filtering criteria to narrow the list of orders returned. If NextToken is present, that will be used to retrieve the orders instead of other criteria. """
		data = dict(
			CreatedAfter=created_after,
			CreatedBefore=created_before,
			LastUpdatedAfter=last_updated_after,
			LastUpdatedBefore=last_updated_before,
			BuyerEmail=buyer_email,
			SellerOrderId=seller_order_id,
			MaxResultsPerPage=max_results,
			NextToken=next_token,
			ActualFulfillmentSupplySourceId=actual_fulfillment_supply_source_id,
			IsISPU=is_ispu,
			StoreChainStoreId=store_chain_store_id
		)

		self.list_to_dict("OrderStatuses", order_statuses, data)
		self.list_to_dict("MarketplaceIds", marketplace_ids, data)
		self.list_to_dict("FulfillmentChannels", fulfillment_channels, data)
		self.list_to_dict("PaymentMethods", payment_methods, data)
		self.list_to_dict("EasyShipShipmentStatuses", easyship_shipment_statuses, data)
		self.list_to_dict("AmazonOrderIds", amazon_order_ids, data)

		if not marketplace_ids:
			marketplace_ids = [self.marketplace_id]
			data["MarketplaceIds"] = marketplace_ids

		return self.make_request(params=data)

	def get_order(self, order_id:str) -> object:
		""" Returns the order indicated by the specified order ID. """
		append_to_base_uri = f"/{order_id}"
		return self.make_request(append_to_base_uri=append_to_base_uri)
	
	def get_order_buyer_info(self, order_id:str) -> object:
		""" Returns buyer information for the specified order. """
		append_to_base_uri = f"/{order_id}/buyerInfo"
		return self.make_request(append_to_base_uri=append_to_base_uri)

	def get_order_address(self, order_id:str) -> object:
		""" Returns the shipping address for the specified order. """
		append_to_base_uri = f"/{order_id}/address"
		return self.make_request(append_to_base_uri=append_to_base_uri)

	def get_order_items(self, order_id:str, next_token:str|None=None) -> object:
		""" Returns detailed order item information for the order indicated by the specified order ID. If NextToken is provided, it's used to retrieve the next page of order items. """
		append_to_base_uri = f"/{order_id}/orderItems"
		data = dict(
			NextToken=next_token
		)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)
	
	def get_order_items_buyer_info(self, order_id:str, next_token:str|None=None) -> object:
		""" Returns buyer information for the order items in the specified order. """
		append_to_base_uri = f"/{order_id}/orderItems/buyerInfo"
		data = dict(
			NextToken=next_token
		)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)
	
	def update_shipment_status(self, order_id:str, marketplace_id:str, shipment_status:str, order_items:list[dict]) -> object:
		""" Update the shipment status. """
		valid_shipment_statuses = ["ReadyForPickup", "PickedUp", "RefusedPickup"]
		if shipment_status not in valid_shipment_statuses:
			raise SPAPIError(f"Invalid Shipment Status: {shipment_status}, valid statuses are {', '.join(map(str, valid_shipment_statuses))}.")

		append_to_base_uri = f"/{order_id}/shipment"
		data = {
			"marketplaceId": marketplace_id,
			"shipmentStatus": shipment_status,
			"orderItems": order_items
		}

		return self.make_request(method="POST", append_to_base_uri=append_to_base_uri, params=data)

class ProductFees(SPAPI):
	pass

class CatalogItems(SPAPI):
	pass

class Pricing(SPAPI):
	pass

class Reports(SPAPI):
	pass

class Sellers(SPAPI):
	pass

class Util:
	@staticmethod
	def get_marketplace_data(selling_region, country_code):
		marketplace = MARKETPLACES.get(selling_region)

		error_msg = ""

		if marketplace:
			region = marketplace.get("AWS Region")
			endpoint = marketplace.get("Endpoint")
			marketplace_id = marketplace.get(country_code)

			if marketplace_id:
				return region, endpoint, marketplace_id
			else:
				error_msg = f"Country Code: {country_code} not found in Selling Region: {selling_region}"
		else:
			error_msg = f"Invalid Selling Region: {selling_region}"
		
		raise SPAPIError(error_msg)
	
	@staticmethod
	def remove_empty(dict):
		"""
	        Helper function that removes all keys from a dictionary (dict), that have an empty value.
		"""
		for key in list(dict):
			if not dict[key]:
				del dict[key]
		return dict
