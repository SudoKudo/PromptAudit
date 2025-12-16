<?php
/*
* Classes for dealing with a DPS PxPay result request
* copyright (c) 2013 WebAware Pty Ltd, released under GPL v2.1
*/

/**
* DPS PxPay result request
*/
class GFDpsPxPayResult {
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
	* encrypted transaction result, to be decrypted by DPS PxPay service
	* @var string
	*/
	public $result;

	/**
	* populate members with defaults, and set account and environment information
	* @param string $userID DPS PxPay account ID
	* @param string $userKey DPS PxPay encryption key
	*/
	public function __construct($userID, $userKey) {
		$this->sslVerifyPeer = true;
		$this->userID = $userID;
		$this->userKey = $userKey;
	}

	/**
	* process a result against DPS PxPay; throws exception on error with error described in exception message.
	*/
	public function processResult() {
		$xml = $this->getResultXML();
		return $this->sendResultRequest($xml);
	}

	/**
	* create XML request document for result parameters
	* @return string
	*/
	public function getResultXML() {
		$xml = new XMLWriter();
		$xml->openMemory();
		$xml->startDocument('1.0', 'UTF-8');
		$xml->startElement('ProcessResponse');

		$xml->writeElement('PxPayUserId', substr($this->userID, 0, 32));
		$xml->writeElement('PxPayKey', substr($this->userKey, 0, 64));
		$xml->writeElement('Response', $this->result);

		$xml->endElement();		// ProcessResponse

		return $xml->outputMemory();
	}

	/**
	* send the DPS PxPay payment request and retrieve and parse the response
	* @param string $xml DPS PxPay payment request as an XML document, per DPS PxPay specifications
	* @return GFDpsPxPayResultResponse
	* @throws GFDpsPxPayException
	*/
	protected function sendResultRequest($xml) {
		// execute the cURL request, and retrieve the response
		try {
			$responseXML = GFDpsPxPayPlugin::curlSendRequest($xml, $this->sslVerifyPeer);
		}
		catch (GFDpsPxPayCurlException $e) {
			throw new GFDpsPxPayException("Error posting DPS PxPay result request: " . $e->getMessage());
		}

		$response = new GFDpsPxPayResultResponse();
		$response->loadResponseXML($responseXML);
		return $response;
	}
}

/**
* DPS PxPay payment result response
*/
class GFDpsPxPayResultResponse {
	/**
	* whether it was a successful request
	* @var boolean
	*/
	public $isValid;

	/**
	* For a successful transaction "True" is passed and for a failed transaction "False" is passed.
	* @var boolean
	*/
	public $success;

	/**
	* total amount of payment as processed, in dollars and cents as a floating-point number
	* @var float
	*/
	public $amount;

	/**
	* If the transaction is successful, this is the bank authorisation number.
	* @var string max. 22 characters
	*/
	public $authCode;

	/**
	* name on credit card
	* @var string max. 64 characters
	*/
	public $cardHoldersName;

	/**
	* name of credit card, e.g. Visa, Mastercard, Amex, Diners
	* @var string max. 16 characters
	*/
	public $cardName;

	/**
	* credit card number, with no spaces, obfuscated
	* @var string max. 16 characters
	*/
	public $cardNumber;

	/**
	* month of expiry, as MM
	* @var string max. 2 digits
	*/
	public $cardExpiryMonth;

	/**
	* year of expiry, as YY
	* @var string max. 2 digits
	*/
	public $cardExpiryYear;

	/**
	* NB. This number is returned as 'DpsTxnRef'
	* @var string max. 16 characters
	*/
	public $txnRef;

	/**
	* textual response status, e.g. APPROVED
	* @var string max. 32 characters
	*/
	public $statusText;

	/**
	* DPS-generated billing ID for recurring payments
	* @var string max. 16 characters
	*/
	public $recurringID;

	/**
	* the currency of the settlement
	* @var string max. 4 characters
	*/
	public $currencySettlement;

	/**
	* the currency of the payment request
	* @var string max. 4 characters
	*/
	public $currencyInput;

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
	* an invoice reference to track by
	* @var string max. 64 characters
	*/
	public $invoiceReference;

	/**
	* IP address of the client
	* @var string
	*/
	public $clientIP;

	/**
	* transaction number passed in payment request
	* @var string max. 16 characters
	*/
	public $transactionNumber;

	/**
	* customer's email address
	* @var string max. 255 characters
	*/
	public $emailAddress;

	/**
	* additional billing ID for recurring payments as passed in payment request
	* @var string max. 32 characters
	*/
	public $billingID;

	/**
	* indication of uniqueness of card number
	* @var string
	*/
	public $txnMac;

	/**
	* a token generated by DPS when adding a card for recurring billing
	* @var string max. 16 characters
	*/
	public $cardNumber2;

	/**
	* CVC / CVV2 Result Code associated with the result of the CVC validation
	* @var string max. 1 character
	*/
	public $cvc2ResultCode;

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
			$this->success = !!((int) $xml->Success);
			$this->amount = (float) $xml->AmountSettlement;
			$this->authCode = (string) $xml->AuthCode;
			$this->cardHoldersName = (string) $xml->CardHolderName;
			$this->cardName = (string) $xml->CardName;
			$this->cardNumber = (string) $xml->CardNumber;
			$this->txnRef = (string) $xml->DpsTxnRef;
			$this->statusText = (string) $xml->ResponseText;
			$this->recurringID = (string) $xml->DpsBillingId;
			$this->currencySettlement = (string) $xml->CurrencySettlement;
			$this->currencyInput = (string) $xml->CurrencyInput;
			$this->option1 = (string) $xml->TxnData1;
			$this->option2 = (string) $xml->TxnData2;
			$this->option3 = (string) $xml->TxnData3;
			$this->txnType = (string) $xml->TxnType;
			$this->invoiceReference = (string) $xml->MerchantReference;
			$this->clientIP = (string) $xml->ClientInfo;
			$this->transactionNumber = (string) $xml->TxnId;
			$this->emailAddress = (string) $xml->EmailAddress;
			$this->billingID = (string) $xml->BillingId;
			$this->txnMac = (string) $xml->TxnMac;
			$this->cardNumber2 = (string) $xml->CardNumber2;
			$this->cvc2ResultCode = (string) $xml->Cvc2ResultCode;

			$cardExpiry = (string) $xml->DateExpiry;
			$this->cardExpiryMonth = substr($cardExpiry, 0, 2);
			$this->cardExpiryYear = substr($cardExpiry, 2, 2);

			// restore old libxml settings
			libxml_disable_entity_loader($oldDisableEntityLoader);
			libxml_use_internal_errors($oldUseInternalErrors);
		}
		catch (Exception $e) {
			// restore old libxml settings
			libxml_disable_entity_loader($oldDisableEntityLoader);
			libxml_use_internal_errors($oldUseInternalErrors);

			throw new GFDpsPxPayException('Error parsing DPS PxPay result request: ' . $e->getMessage());
		}

		// if response is "invalid", throw error with message given in statusText field
		if (!$this->isValid) {
			throw new GFDpsPxPayException('Error from DPS PxPay result: ' . $this->statusText);
		}
	}
}
