import hmac
import hashlib
import datetime
from requests.auth import AuthBase
from requests.compat import urlparse


class AWSSigV4(AuthBase):
    
    def __init__(self, service, **kwargs):
        """ Create authentication mechanism
        
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
        """ Called to add authentication information to request
        
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
            query_string = dict(map(lambda i: i.split("="), parsed_url.query.split("&")))
        else:
            query_string = dict()
        
        # Setup Headers.
        if "Host" not in request.headers:
            request.headers["Host"] = host
        if "Content-Type" not in request.headers:
            request.headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        if "User-Agent" not in request.headers:
            request.headers["User-Agent"] = "python-amazon-mws/0.0.1 (Language=Python)"
        if self.aws_session_token:
            request.headers["x-amz-security-token"] = self.aws_session_token
        request.headers["X-AMZ-Date"] = self.amzdate

        # ************* TASK 1: CREATE A CANONICAL REQUEST *************
        # http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html

        # Query string values must be URL-encoded (space=%20) and be sorted by name.
        canonical_query_string = "&".join(map(lambda p: "=".join(p), sorted(query_string.items())))
        
        # Create payload hash (hash of the request body content).
        if request.method == "GET":
            payload_hash = hashlib.sha256(("").encode("utf-8")).hexdigest()
        else:
            if request.body:
                if isinstance(request.body, bytes):
                    payload_hash = hashlib.sha256(request.body).hexdigest()
                else:
                    payload_hash = hashlib.sha256(request.body.encode("utf-8")).hexdigest()
            else:
                payload_hash = hashlib.sha256(b"").hexdigest()
        request.headers["x-amz-content-sha256"] = payload_hash
        
        # Create the canonical headers and signed headers. Header names
        # must be trimmed and lowercase, and sorted in code point order from
        # low to high. Note that there is a trailing \n.
        headers_to_sign = sorted(filter(lambda h: h.startswith("x-amz-") or h == "host",
            map(lambda H: H.lower(), request.headers.keys())))
        canonical_headers = "".join(map(lambda h: ":".join((h, request.headers[h])) + "\n", headers_to_sign))
        signed_headers = ";".join(headers_to_sign)
        
        # Combine elements to create canonical request.
        canonical_request = "\n".join([request.method, uri, canonical_query_string, 
            canonical_headers, signed_headers, payload_hash])
        
        # ************* TASK 2: CREATE THE STRING TO SIGN*************
        credential_scope = "/".join([self.datestamp, self.region, self.service, "aws4_request"])
        string_to_sign = "\n".join(["AWS4-HMAC-SHA256", self.amzdate, 
            credential_scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()])
        
        # ************* TASK 3: CALCULATE THE SIGNATURE *************
        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        key_date = sign(("AWS4" + self.aws_secret_access_key).encode("utf-8"), self.datestamp)
        key_region = sign(key_date, self.region)
        k_service = sign(key_region, self.service)
        key_signing = sign(k_service, "aws4_request")
        signature = hmac.new(key_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        
        # ************* TASK 4: ADD SIGNING INFORMATION TO THE REQUEST *************
        request.headers["Authorization"] = f"AWS4-HMAC-SHA256 Credential={self.aws_access_key_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

        return request
