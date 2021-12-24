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
	pass

class SPAPI(object):
	pass

class Feeds(SPAPI):
	pass

class Finances(SPAPI):
	pass

class FBAInventory(SPAPI):
	pass

class Orders(SPAPI):
	pass

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
