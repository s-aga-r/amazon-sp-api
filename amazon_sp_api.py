import hmac
import boto3
import hashlib
import datetime

from requests import request
from requests.auth import AuthBase
from requests.models import Response
from requests.compat import urlparse


__all__ = [
    "SPAPIError",
    # "SPAPI"
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

# Following code is adapted from https://github.com/andrewjroth/requests-auth-aws-sigv4 under the Apache License 2.0 with minor changes.

# Copyright 2020 Andrew J Roth <andrew@andrewjroth.com>

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.


class AWSSigV4(AuthBase):
    def __init__(self, service, **kwargs):
        """Create authentication mechanism

        :param service: AWS Service identifier, for example `ec2`.  This is required.
        :param region:  AWS Region, for example `us-east-1`.  If not provided, it will be set using
            the environment variables `AWS_DEFAULT_REGION` or using boto3, if available.
        :param session: If boto3 is available, will attempt to get credentials using boto3,
            unless passed explicitly.  If using boto3, the provided session will be used or a new
            session will be created.

        """

        self.service = service
        self.region = kwargs.get("region")
        self.aws_access_key_id = kwargs.get("aws_access_key_id")
        self.aws_session_token = kwargs.get("aws_session_token")
        self.aws_secret_access_key = kwargs.get("aws_secret_access_key")

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise KeyError("AWS Access Key ID and Secret Access Key are required.")

        if self.region is None:
            raise KeyError("Region is required.")

    def __call__(self, request):
        """Called to add authentication information to request

        :param request: `requests.models.PreparedRequest` object to modify

        :returns: `requests.models.PreparedRequest`, modified to add authentication

        """

        # Create a date for headers and the credential string.
        time = datetime.datetime.utcnow()
        self.amzdate = time.strftime("%Y%m%dT%H%M%SZ")
        self.datestamp = time.strftime("%Y%m%d")

        # Parse request to get URL parts.
        parsed_url = urlparse(request.url)
        host = parsed_url.hostname
        uri = parsed_url.path

        if len(parsed_url.query) > 0:
            query_string = dict(
                map(lambda i: i.split("="), parsed_url.query.split("&"))
            )
        else:
            query_string = dict()

        # Setup Headers.
        if "Host" not in request.headers:
            request.headers["Host"] = host
        if "Content-Type" not in request.headers:
            request.headers[
                "Content-Type"
            ] = "application/x-www-form-urlencoded; charset=utf-8"
        if "User-Agent" not in request.headers:
            request.headers["User-Agent"] = "python-amazon-mws/0.0.1 (Language=Python)"
        if self.aws_session_token:
            request.headers["x-amz-security-token"] = self.aws_session_token
        request.headers["X-AMZ-Date"] = self.amzdate

        # ************* TASK 1: CREATE A CANONICAL REQUEST *************
        # http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html

        # Query string values must be URL-encoded (space=%20) and be sorted by name.
        canonical_query_string = "&".join(
            map(lambda p: "=".join(p), sorted(query_string.items()))
        )

        # Create payload hash (hash of the request body content).
        if request.method == "GET":
            payload_hash = hashlib.sha256(("").encode("utf-8")).hexdigest()
        else:
            if request.body:
                if isinstance(request.body, bytes):
                    payload_hash = hashlib.sha256(request.body).hexdigest()
                else:
                    payload_hash = hashlib.sha256(
                        request.body.encode("utf-8")
                    ).hexdigest()
            else:
                payload_hash = hashlib.sha256(b"").hexdigest()
        request.headers["x-amz-content-sha256"] = payload_hash

        # Create the canonical headers and signed headers. Header names
        # must be trimmed and lowercase, and sorted in code point order from
        # low to high. Note that there is a trailing \n.
        headers_to_sign = sorted(
            filter(
                lambda h: h.startswith("x-amz-") or h == "host",
                map(lambda H: H.lower(), request.headers.keys()),
            )
        )
        canonical_headers = "".join(
            map(lambda h: ":".join((h, request.headers[h])) + "\n", headers_to_sign)
        )
        signed_headers = ";".join(headers_to_sign)

        # Combine elements to create canonical request.
        canonical_request = "\n".join(
            [
                request.method,
                uri,
                canonical_query_string,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        # ************* TASK 2: CREATE THE STRING TO SIGN*************
        credential_scope = "/".join(
            [self.datestamp, self.region, self.service, "aws4_request"]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                self.amzdate,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        # ************* TASK 3: CALCULATE THE SIGNATURE *************
        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        key_date = sign(
            ("AWS4" + self.aws_secret_access_key).encode("utf-8"), self.datestamp
        )
        key_region = sign(key_date, self.region)
        k_service = sign(key_region, self.service)
        key_signing = sign(k_service, "aws4_request")
        signature = hmac.new(
            key_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # ************* TASK 4: ADD SIGNING INFORMATION TO THE REQUEST *************
        request.headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.aws_access_key_id}/{credential_scope},"
            f" SignedHeaders={signed_headers}, Signature={signature}"
        )

        return request


class SPAPIError(Exception):
    """
    Main SP-API Exception class
    """

    def __init__(self, *args, **kwargs) -> None:
        self.error = kwargs.get("error", "-")
        self.error_description = kwargs.get("error_description", "-")
        super().__init__(*args)


class SPAPI(object):
    """Base Amazon SP-API class"""

    # https://github.com/amzn/selling-partner-api-docs/blob/main/guides/en-US/developer-guide/SellingPartnerApiDeveloperGuide.md#connecting-to-the-selling-partner-api
    AUTH_URL = "https://api.amazon.com/auth/o2/token"

    BASE_URI = "/"

    def __init__(
        self,
        iam_arn: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        aws_access_key: str,
        aws_secret_key: str,
        country_code: str = "US",
    ) -> None:
        self.iam_arn = iam_arn
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.country_code = country_code
        self.region, self.endpoint, self.marketplace_id = Util.get_marketplace_data(
            country_code
        )

    def get_access_token(self) -> str:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }

        response = request(method="POST", url=self.AUTH_URL, data=data)
        result = response.json()
        if response.status_code == 200:
            return result.get("access_token")
        exception = SPAPIError(
            error=result.get("error"), error_description=result.get("error_description")
        )
        raise exception

    def get_auth(self) -> AWSSigV4:
        client = boto3.client(
            "sts",
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region,
        )

        response = client.assume_role(
            RoleArn=self.iam_arn, RoleSessionName="SellingPartnerAPI"
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
            region=self.region,
        )

    def get_headers(self) -> dict:
        return {"x-amz-access-token": self.get_access_token()}

    def make_request(
        self,
        method: str = "GET",
        append_to_base_uri: str = "",
        params: dict = None,
        data: dict = None,
    ) -> Response:
        if isinstance(params, dict):
            params = Util.remove_empty(params)
        if isinstance(data, dict):
            data = Util.remove_empty(data)

        url = self.endpoint + self.BASE_URI + append_to_base_uri

        return request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=self.get_headers(),
            auth=self.get_auth(),
        )

    def list_to_dict(self, key: str, values: list, data: dict) -> None:
        if values and isinstance(values, list):
            for idx in range(len(values)):
                data[f"{key}[{idx}]"] = values[idx]


class Feeds(SPAPI):
    pass


class Finances(SPAPI):
    """Amazon Finances API"""

    BASE_URI = "/finances/v0/"

    def list_financial_event_groups(
        self,
        max_results: int = None,
        started_before: str = None,
        started_after: str = None,
        next_token: str = None,
    ) -> Response:
        """Returns financial event groups for a given date range."""
        append_to_base_uri = "financialEventGroups"
        data = dict(
            MaxResultsPerPage=max_results,
            FinancialEventGroupStartedBefore=started_before,
            FinancialEventGroupStartedAfter=started_after,
            NextToken=next_token,
        )
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def list_financial_events_by_group_id(
        self, group_id: str, max_results: int = None, next_token: str = None
    ) -> Response:
        """Returns all financial events for the specified financial event group."""
        append_to_base_uri = f"financialEventGroups/{group_id}/financialEvents"
        data = dict(MaxResultsPerPage=max_results, NextToken=next_token)
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def list_financial_events_by_order_id(
        self, order_id: str, max_results: int = None, next_token: str = None
    ) -> Response:
        """Returns all financial events for the specified order."""
        append_to_base_uri = f"orders/{order_id}/financialEvents"
        data = dict(MaxResultsPerPage=max_results, NextToken=next_token)
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def list_financial_events(
        self,
        max_results: int = None,
        posted_after: str = None,
        posted_before: str = None,
        next_token: str = None,
    ) -> Response:
        """Returns financial events for the specified data range."""
        append_to_base_uri = f"financialEvents"
        data = dict(
            MaxResultsPerPage=max_results,
            PostedAfter=posted_after,
            PostedBefore=posted_before,
            NextToken=next_token,
        )
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)


class FBAInventory(SPAPI):
    """Amazon FBAInventory API"""

    BASE_URI = "/fba/inventory/v1/summaries"

    def get_inventory_summaries(
        self,
        granularity_id: str,
        details: bool = None,
        start_date_time: str = None,
        seller_skus: list = None,
        next_token: str = None,
        marketplace_ids: list = None,
    ) -> Response:
        """Returns a list of inventory summaries. The summaries returned depend on the presence or absence of the startDateTime and sellerSkus parameters:

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
    """Amazon Orders API"""

    BASE_URI = "/orders/v0/orders"

    def get_orders(
        self,
        created_after: str,
        created_before: str = None,
        last_updated_after: str = None,
        last_updated_before: str = None,
        order_statuses: list = None,
        marketplace_ids: list = None,
        fulfillment_channels: list = None,
        payment_methods: list = None,
        buyer_email: str = None,
        seller_order_id: str = None,
        max_results: int = 100,
        easyship_shipment_statuses: list = None,
        next_token: str = None,
        amazon_order_ids: list = None,
        actual_fulfillment_supply_source_id: str = None,
        is_ispu: bool = False,
        store_chain_store_id: str = None,
    ) -> Response:
        """Returns orders created or updated during the time frame indicated by the specified parameters. You can also apply a range of filtering criteria to narrow the list of orders returned. If NextToken is present, that will be used to retrieve the orders instead of other criteria."""
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
            StoreChainStoreId=store_chain_store_id,
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

    def get_order(self, order_id: str) -> Response:
        """Returns the order indicated by the specified order ID."""
        append_to_base_uri = f"/{order_id}"
        return self.make_request(append_to_base_uri=append_to_base_uri)

    def get_order_buyer_info(self, order_id: str) -> Response:
        """Returns buyer information for the specified order."""
        append_to_base_uri = f"/{order_id}/buyerInfo"
        return self.make_request(append_to_base_uri=append_to_base_uri)

    def get_order_address(self, order_id: str) -> Response:
        """Returns the shipping address for the specified order."""
        append_to_base_uri = f"/{order_id}/address"
        return self.make_request(append_to_base_uri=append_to_base_uri)

    def get_order_items(self, order_id: str, next_token: str = None) -> Response:
        """Returns detailed order item information for the order indicated by the specified order ID. If NextToken is provided, it's used to retrieve the next page of order items."""
        append_to_base_uri = f"/{order_id}/orderItems"
        data = dict(NextToken=next_token)
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def get_order_items_buyer_info(
        self, order_id: str, next_token: str = None
    ) -> Response:
        """Returns buyer information for the order items in the specified order."""
        append_to_base_uri = f"/{order_id}/orderItems/buyerInfo"
        data = dict(NextToken=next_token)
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def update_shipment_status(
        self,
        order_id: str,
        marketplace_id: str,
        shipment_status: str,
        order_items: list,
    ) -> Response:
        """Update the shipment status."""
        valid_shipment_statuses = ["ReadyForPickup", "PickedUp", "RefusedPickup"]
        if shipment_status not in valid_shipment_statuses:
            raise SPAPIError(
                f"Invalid Shipment Status: {shipment_status}, valid statuses are {', '.join(map(str, valid_shipment_statuses))}."
            )

        append_to_base_uri = f"/{order_id}/shipment"
        data = {
            "marketplaceId": marketplace_id,
            "shipmentStatus": shipment_status,
            "orderItems": order_items,
        }

        return self.make_request(
            method="POST", append_to_base_uri=append_to_base_uri, data=data
        )


class ProductFees(SPAPI):
    pass


class CatalogItems(SPAPI):
    """Amazon Catalog Items API"""

    BASE_URI = "/catalog/2020-12-01/items"

    def search_catalog_items(
        self,
        keywords: list,
        marketplace_ids: list = None,
        included_data: list = None,
        brand_names: list = None,
        classification_ids: list = None,
        page_size: int = None,
        page_token: str = None,
        keywords_locale: str = None,
        locale: str = None,
    ) -> Response:
        """Search for and return a list of Amazon catalog items and associated information."""
        valid_included_data = [
            "IDENTIFIERS",
            "IMAGES",
            "PRODUCTTYPES",
            "SALESRANKS",
            "SUMMARIES",
            "VARIATIONS",
            "VENDORDETAILS",
        ]
        if included_data:
            for item in included_data:
                if item.upper() not in valid_included_data:
                    raise SPAPIError(
                        f"Invalid Included Data: {item}, allowed data {', '.join(map(str, valid_included_data))}."
                    )

        data = dict(
            pageSize=page_size,
            pageToken=page_token,
            keywordsLocale=keywords_locale,
            locale=locale,
        )

        self.list_to_dict("keywords", keywords, data)
        self.list_to_dict("marketplaceIds", marketplace_ids, data)
        self.list_to_dict("includedData", included_data, data)
        self.list_to_dict("brandNames", brand_names, data)
        self.list_to_dict("classificationIds", classification_ids, data)

        if not marketplace_ids:
            marketplace_ids = [self.marketplace_id]
            data["marketplaceIds"] = marketplace_ids

        return self.make_request(params=data)

    def get_catalog_item(
        self,
        asin: str,
        marketplace_ids: list = None,
        included_data: list = None,
        locale: str = None,
    ) -> Response:
        """Retrieves details for an item in the Amazon catalog."""
        valid_included_data = [
            "ATTRIBUTES",
            "IDENTIFIERS",
            "IMAGES",
            "PRODUCTTYPES",
            "SALESRANKS",
            "SUMMARIES",
            "VARIATIONS",
            "VENDORDETAILS",
        ]
        if included_data:
            for item in included_data:
                if item.upper() not in valid_included_data:
                    raise SPAPIError(
                        f"Invalid Included Data: {item}, allowed data {', '.join(map(str, valid_included_data))}."
                    )

        append_to_base_uri = f"/{asin}"
        data = dict(locale=locale)

        self.list_to_dict("marketplaceIds", marketplace_ids, data)
        self.list_to_dict("includedData", included_data, data)

        if not marketplace_ids:
            marketplace_ids = [self.marketplace_id]
            data["marketplaceIds"] = marketplace_ids

        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)


class Pricing(SPAPI):
    pass


class Reports(SPAPI):
    """Amazon Reports API"""

    BASE_URI = "/reports/2021-06-30"

    def get_reports(
        self,
        report_types: list = None,
        processing_statuses: list = None,
        marketplace_ids: list = None,
        page_size: int = None,
        created_since: str = None,
        created_until: str = None,
        next_token: str = None,
    ) -> Response:
        """Returns report details for the reports that match the filters that you specify."""
        valid_processing_statuses = [
            "CANCELLED",
            "DONE",
            "FATAL",
            "IN_PROGRESS",
            "IN_QUEUE",
        ]
        if processing_statuses:
            for processing_status in processing_statuses:
                if processing_status.upper() not in valid_processing_statuses:
                    raise SPAPIError(
                        f"Invalid Processing Status: {processing_status}, valid statuses are {', '.join(map(str, valid_processing_statuses))}."
                    )

        append_to_base_uri = "/reports"
        data = dict(
            pageSize=page_size,
            createdSince=created_since,
            createdUntil=created_until,
            nextToken=next_token,
        )

        self.list_to_dict("reportTypes", report_types, data)
        self.list_to_dict("processingStatuses", processing_statuses, data)
        self.list_to_dict("marketplaceIds", marketplace_ids, data)

        if not marketplace_ids:
            marketplace_ids = [self.marketplace_id]
            data["marketplaceIds"] = marketplace_ids

        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def create_report(
        self,
        report_type: str,
        report_options: dict = None,
        data_start_time: str = None,
        data_end_time: str = None,
        marketplace_ids: list = None,
    ) -> Response:
        """Creates a report."""
        append_to_base_uri = "/reports"
        data = dict(
            reportType=report_type,
            reportOptions=report_options,
            dataStartTime=data_start_time,
            dataEndTime=data_end_time,
        )

        self.list_to_dict("marketplaceIds", marketplace_ids, data)

        if not marketplace_ids:
            marketplace_ids = [self.marketplace_id]
            data["marketplaceIds"] = marketplace_ids

        return self.make_request(
            method="POST", append_to_base_uri=append_to_base_uri, data=data
        )

    def get_report(self, report_id: str) -> Response:
        """Returns report details (including the reportDocumentId, if available) for the report that you specify."""
        append_to_base_uri = f"/reports/{report_id}"
        return self.make_request(append_to_base_uri=append_to_base_uri)

    def cancel_report(self, report_id: str) -> Response:
        """Cancels the report that you specify. Only reports with processingStatus=IN_QUEUE can be cancelled. Cancelled reports are returned in subsequent calls to the getReport and getReports operations."""
        append_to_base_uri = f"/reports/{report_id}"
        return self.make_request(method="DELETE", append_to_base_uri=append_to_base_uri)

    def get_report_schedules(self, report_types: list) -> Response:
        """Returns report schedule details that match the filters that you specify."""
        append_to_base_uri = "/schedules"
        data = {}
        self.list_to_dict("reportTypes", report_types, data)
        return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

    def create_report_schedule(
        self,
        report_type: str,
        period: str,
        marketplace_ids: list = None,
        report_options: dict = None,
        next_report_creation_time: str = None,
    ) -> object:
        """Creates a report schedule. If a report schedule with the same report type and marketplace IDs already exists, it will be cancelled and replaced with this one."""
        valid_periods = [
            "PT5M",
            "PT15M",
            "PT30M",
            "PT1H",
            "PT2H",
            "PT4H",
            "PT8H",
            "PT12H",
            "P1D",
            "P2D",
            "P3D",
            "PT84H",
            "P7D",
            "P14D",
            "P15D",
            "P18D",
            "P30D",
            "P1M",
        ]
        if period not in valid_periods:
            raise SPAPIError(
                f"Invalid Period: {period}, valid periods are {', '.join(map(str, valid_periods))}."
            )

        append_to_base_uri = "/schedules"
        data = dict(
            reportType=report_type,
            reportOptions=report_options,
            period=period,
            nextReportCreationTime=next_report_creation_time,
        )

        self.list_to_dict("marketplaceIds", marketplace_ids, data)

        if not marketplace_ids:
            marketplace_ids = [self.marketplace_id]
            data["marketplaceIds"] = marketplace_ids

        return self.make_request(
            method="POST", append_to_base_uri=append_to_base_uri, data=data
        )

    def get_report_schedule(self, report_schedule_id: str) -> Response:
        """Returns report schedule details for the report schedule that you specify."""
        append_to_base_uri = f"/schedules/{report_schedule_id}"
        return self.make_request(append_to_base_uri=append_to_base_uri)

    def cancel_report_schedule(self, report_schedule_id: str) -> Response:
        """Cancels the report schedule that you specify."""
        append_to_base_uri = f"/schedules/{report_schedule_id}"
        return self.make_request(method="DELETE", append_to_base_uri=append_to_base_uri)

    def get_report_document(self, report_document_id: str) -> Response:
        """Returns the information required for retrieving a report document's contents."""
        append_to_base_uri = f"/documents/{report_document_id}"
        return self.make_request(append_to_base_uri=append_to_base_uri)


class Sellers(SPAPI):
    """Amazon Sellers API"""

    BASE_URI = "/sellers/v1/marketplaceParticipations"

    def get_marketplace_participations(self) -> Response:
        """Returns a list of marketplaces that the seller submitting the request can sell in and information about the seller's participation in those marketplaces."""
        return self.make_request()


class Util:
    @staticmethod
    def get_marketplace(country_code):
        for selling_region in MARKETPLACES:
            for country in MARKETPLACES.get(selling_region):
                if country_code == country:
                    return MARKETPLACES.get(selling_region)
        else:
            raise KeyError(f"Invalid Country Code: {country_code}")

    @staticmethod
    def get_marketplace_data(country_code):
        marketplace = Util.get_marketplace(country_code)
        region = marketplace.get("AWS Region")
        endpoint = marketplace.get("Endpoint")
        marketplace_id = marketplace.get(country_code)

        return region, endpoint, marketplace_id

    @staticmethod
    def remove_empty(dict):
        """
        Helper function that removes all keys from a dictionary (dict), that have an empty value.
        """
        for key in list(dict):
            if not dict[key]:
                del dict[key]
        return dict
