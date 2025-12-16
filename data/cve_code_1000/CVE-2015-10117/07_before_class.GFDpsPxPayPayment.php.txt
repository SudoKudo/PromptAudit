<?php
/*
* Classes for dealing with a DPS PxPay payment request
* copyright (c) 2013 WebAware Pty Ltd, released under GPL v2.1
*/

/**
* DPS PxPay payment request
*/
class GFDpsPxPayPayment {
	// environment / website specific members
	/**
	* default true, whether to validate the remote SSL certificate
	* @var boolean
	*/
	public $sslVerifyPeer;

	// payment specific members
	/**
	* account name / email address at DPS PxPay
	* @var string max. 8 characters
	*/
	public $userID;

	/**
	* account name / email address at DPS PxPay
	* @var string max. 8 characters
	*/
	public $userKey;

	/**
	* total amount of payment, in dollars and cents as a floating-point number
	* @var float
	*/
	public $amount;

	/**
	* additional billing ID for recurring payments
	* @var string max. 32 characters
	*/
	public $billingID;

	/**
	* flag for enabling recurring billing
	* @var string max. 1 character
	*/
	public $enableRecurring;

	/**
	* currency code (AUD, NZD, etc.)
	* @var string max. 4 characters
	*/
	public $currency;

	/**
	* customer's email address
	* @var string max. 255 characters
	*/
	public $emailAddress;

	/**
	* an invoice reference to track by
	* @var string max. 64 characters
	*/
	public $invoiceReference;

	/**
	* an optional invoice description
	* @var string max. 64 characters
	*/
	public $invoiceDescription;

	/**
	* optional additional information for use in shopping carts, etc.
	* @var string max. 255 characters
	*/
	public $option1;

	/**
	* optional additional information for use in shopping carts, etc.
	* @var string max. 255 characters
	*/
	public $option2;

	/**
	* optional additional information for use in shopping carts, etc.
	* @var string max. 255 characters
	*/
	public $option3;

	/**
	* type of transaction (Purchase, Auth)
	* @var string max. 8 characters
	*/
	public $txnType;

	/**
	* URL to redirect to on failure
	* @var string max. 255 characters
	*/
	public $urlFail;

	/**
	* URL to redirect to on success
	* @var string max. 255 characters
	*/
	public $urlSuccess;

	/**
	* transaction number
	* @var string max. 16 characters
	*/
	public $transactionNumber;

	/**
	* populate members with defaults, and set account and environment information
	*
	* @param string $userID DPS PxPay account ID
	* @param string $userKey DPS PxPay encryption key
	*/
	public function __construct($userID, $userKey) {
		$this->sslVerifyPeer = true;
		$this->userID = $userID;
		$this->userKey = $userKey;

		// default to single payment, not recurring
		$this->enableRecurring = false;
	}

	/**
	* process a payment against DPS PxPay; throws exception on error with error described in exception message.
	*/
	public function processPayment() {
		$this->validate();
		$xml = $this->getPaymentXML();
		return $this->sendPaymentRequest($xml);
	}

	/**
	* validate the data members to ensure that sufficient and valid information has been given
	* @throws GFDpsPxPayException
	*/
	protected function validate() {
		$errmsg = '';

		if (strlen($this->userID) === 0)
			$errmsg .= "userID cannot be empty.\n";
		if (strlen($this->userKey) === 0)
			$errmsg .= "userKey cannot be empty.\n";
		if (!is_numeric($this->amount) || $this->amount <= 0)
			$errmsg .= "amount must be given as a number in dollars and cents.\n";
		else if (!is_float($this->amount))
			$this->amount = (float) $this->amount;
		if (strlen($this->currency) === 0)
			$errmsg .= "currency cannot be empty.\n";
		if (strlen($this->invoiceReference) === 0)
			$errmsg .= "invoice reference cannot be empty.\n";
		if (strlen($this->txnType) === 0)
			$errmsg .= "transaction type cannot be empty.\n";
		if (strlen($this->urlFail) === 0)
			$errmsg .= "URL for transaction fail cannot be empty.\n";
		if (strlen($this->urlSuccess) === 0)
			$errmsg .= "URL for transaction success cannot be empty.\n";

		if (strlen($errmsg) > 0) {
			throw new GFDpsPxPayException($errmsg);
		}
	}

	/**
	* create XML request document for payment parameters
	* @return string
	*/
	public function getPaymentXML() {
		$xml = new XMLWriter();
		$xml->openMemory();
		$xml->startDocument('1.0', 'UTF-8');
		$xml->startElement('GenerateRequest');

		$xml->writeElement('PxPayUserId', substr($this->userID, 0, 32));
		$xml->writeElement('PxPayKey', substr($this->userKey, 0, 64));
		$xml->writeElement('TxnType', substr($this->txnType, 0, 8));
		$xml->writeElement('AmountInput', number_format($this->amount, 2, '.', ''));
		$xml->writeElement('CurrencyInput', substr($this->currency, 0, 4));
		$xml->writeElement('MerchantReference', substr($this->invoiceReference, 0, 64));
		$xml->writeElement('TxnData1', substr($this->option1, 0, 255));
		$xml->writeElement('TxnData2', substr($this->option2, 0, 255));
		$xml->writeElement('TxnData3', substr($this->option3, 0, 255));
		$xml->writeElement('EmailAddress', substr($this->emailAddress, 0, 255));
		$xml->writeElement('TxnId', substr($this->transactionNumber, 0, 16));
		$xml->writeElement('BillingId', substr($this->billingID, 0, 32));
		$xml->writeElement('EnableAddBillCard', $this->enableRecurring ? '1' : '0');
		$xml->writeElement('UrlSuccess', substr($this->urlSuccess, 0, 255));
		$xml->writeElement('UrlFail', substr($this->urlFail, 0, 255));
		$xml->writeElement('Opt', substr($this->invoiceDescription, 0, 64));

		$xml->endElement();		// GenerateRequest

		return $xml->outputMemory();
	}

	/**
	* send the DPS PxPay payment request and retrieve and parse the response
	* @param string $xml DPS PxPay payment request as an XML document, per DPS PxPay specifications
	* @return GFDpsPxPayPaymentResponse
	* @throws GFDpsPxPayException
	*/
	protected function sendPaymentRequest($xml) {
		// execute the cURL request, and retrieve the response
		try {
			$responseXML = GFDpsPxPayPlugin::curlSendRequest($xml, $this->sslVerifyPeer);
		}
		catch (GFDpsPxPayCurlException $e) {
			throw new GFDpsPxPayException("Error posting DPS PxPay payment request: " . $e->getMessage());
		}

		$response = new GFDpsPxPayPaymentResponse();
		$response->loadResponseXML($responseXML);
		return $response;
	}
}

/**
* DPS PxPay payment request response
*/
class GFDpsPxPayPaymentResponse {
	/**
	* whether it was a successful request
	* @var boolean
	*/
	public $isValid;

	/**
	* URL to redirect browser to where credit card details can be entered
	* @var string
	*/
	public $paymentURL;

	/**
	* load DPS PxPay response data as XML string
	* @param string $response DPS PxPay response as a string (hopefully of XML data)
	* @throws GFDpsPxPayException
	*/
	public function loadResponseXML($response) {
		// prevent XML injection attacks, and handle errors without warnings
		$oldDisableEntityLoader = libxml_disable_entity_loader(TRUE);
		$oldUseInternalErrors = libxml_use_internal_errors(TRUE);

		try {
			$xml = simplexml_load_string($response);
			if ($xml === false) {
				$errmsg = '';
				foreach (libxml_get_errors() as $error) {
					$errmsg .= $error->message;
				}
				throw new Exception($errmsg);
			}

			$this->isValid = ('1' === ((string) $xml['valid']));
			$this->paymentURL = (string) $xml->URI;

			// restore old libxml settings
			libxml_disable_entity_loader($oldDisableEntityLoader);
			libxml_use_internal_errors($oldUseInternalErrors);
		}
		catch (Exception $e) {
			// restore old libxml settings
			libxml_disable_entity_loader($oldDisableEntityLoader);
			libxml_use_internal_errors($oldUseInternalErrors);

			throw new GFDpsPxPayException('Error parsing DPS PxPay generate response: ' . $e->getMessage());
		}

		// if response is "invalid", throw error with message given in URI field
		if (!$this->isValid) {
			throw new GFDpsPxPayException('Error from DPS PxPay generate response: ' . $this->paymentURL);
		}
	}
}
