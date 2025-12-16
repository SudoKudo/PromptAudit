<?php
/*
Plugin Name: Gravity Forms DPS PxPay
Plugin URI: http://shop.webaware.com.au/downloads/gravity-forms-dps-pxpay/
Description: Integrates Gravity Forms with DPS PxPay payment gateway, enabling end users to purchase goods and services through Gravity Forms.
Version: 1.4.3
Author: WebAware
Author URI: http://webaware.com.au/
*/

/*
copyright (c) 2013-2015 WebAware Pty Ltd (email : support@webaware.com.au)

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
*/

if (!defined('ABSPATH')) {
	exit;
}

define('GFDPSPXPAY_PLUGIN_ROOT', dirname(__FILE__) . '/');
define('GFDPSPXPAY_PLUGIN_NAME', basename(dirname(__FILE__)) . '/' . basename(__FILE__));
define('GFDPSPXPAY_PLUGIN_FILE', __FILE__);
define('GFDPSPXPAY_PLUGIN_OPTIONS', 'gfdpspxpay_plugin');
define('GFDPSPXPAY_PLUGIN_VERSION', '1.4.3');

// custom post types
define('GFDPSPXPAY_TYPE_FEED', 'gfdpspxpay_feed');

/**
* autoload classes as/when needed
*
* @param string $class_name name of class to attempt to load
*/
function gfdpspxpay_autoload($class_name) {
	static $classMap = array (
		'GFDpsPxPayAdmin'						=> 'includes/class.GFDpsPxPayAdmin.php',
		'GFDpsPxPayFeed'						=> 'includes/class.GFDpsPxPayFeed.php',
		'GFDpsPxPayFeedAdmin'					=> 'includes/class.GFDpsPxPayFeedAdmin.php',
		'GFDpsPxPayFormData'					=> 'includes/class.GFDpsPxPayFormData.php',
		'GFDpsPxPayPayment'						=> 'includes/class.GFDpsPxPayPayment.php',
		'GFDpsPxPayPlugin'						=> 'includes/class.GFDpsPxPayPlugin.php',
		'GFDpsPxPayResult'						=> 'includes/class.GFDpsPxPayResult.php',
	);

	if (isset($classMap[$class_name])) {
		require GFDPSPXPAY_PLUGIN_ROOT . $classMap[$class_name];
	}
}
spl_autoload_register('gfdpspxpay_autoload');

// instantiate the plug-in
GFDpsPxPayPlugin::getInstance();
