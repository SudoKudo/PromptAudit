<?php
/**
 * @package   Redbit\SimpleShop\WpPlugin
 * @license   MIT
 * @copyright 2016-2023 Redbit s.r.o.
 * @author    Redbit s.r.o. <info@simpleshop.cz>
 */

namespace Redbit\SimpleShop\WpPlugin;

use Exception;
use VyfakturujAPIException;

/**
 * CMB2 Theme Options
 * @version 0.1.0
 * @property-read string $key
 * @property-read string $metabox_id
 * @property-read string $title
 * @property-read string $options_page
 */
class Settings {

	/**
	 * Options Page title
	 * @var string
	 */
	protected $title = '';

	/**
	 * Options Page hook
	 * @var string
	 */
	protected $options_page = '';

	/**
	 * Option key, and option page slug
	 * @var string
	 */
	private $key = 'ssc_options';

	/**
	 * Options page metabox id
	 * @var string
	 */
	private $metabox_id = 'ssc_option_metabox';

	/** @var Plugin */
	private $loader;

	/**
	 * Constructor
	 *
	 * @param Plugin $loader
	 *
	 * @since 0.1.0
	 *
	 */
	public function __construct( Plugin $loader ) {
		// Set our title
		$this->title = __( 'Settings', 'simpleshop-cz' );
		$this->register_hooks();
		$this->loader = $loader;
	}

	/**
	 * Initiate our hooks
	 * @since 0.1.0
	 */
	public function register_hooks() {
		add_action( 'admin_init', [ $this, 'init' ] );
		add_action( 'admin_menu', [ $this, 'add_options_page' ] );
		add_action( 'cmb2_admin_init', [ $this, 'add_options_page_metabox' ] );
		add_filter( 'cmb2_render_disconnect_button', [ $this, 'field_type_disconnect_button' ], 10, 5 );
		add_action( 'admin_init', [ $this, 'maybe_disconnect_simpleshop' ] );
		add_action( 'admin_print_styles', [ $this, 'maybe_display_messages' ] );
	}

	public function field_type_disconnect_button(
		$field,
		$escaped_value,
		$object_id,
		$object_type,
		$field_type_object
	) {
		$url = add_query_arg( [
			'_wpnonce'              => wp_create_nonce(),
			'page'                  => 'ssc_options',
			'disconnect_simpleshop' => 1,
		], admin_url( 'admin.php' ) );

		printf(
			'<a href="%s">%s</a>',
			htmlspecialchars( $url, ENT_QUOTES ),
			__( 'Disconnect SimpleShop', 'simpleshop-cz' )
		);
	}

	/**
	 * Register our setting to WP
	 * @since  0.1.0
	 */
	public function init() {
		register_setting( $this->key, $this->key );
	}

	/**
	 * Add menu options page
	 * @since 0.1.0
	 */
	public function add_options_page() {
		$translatedTitle = $this->title;

		add_submenu_page(
			'simple_shop_settings',
			$translatedTitle,
			$translatedTitle,
			'manage_options',
			'admin.php?page=' . urlencode( $this->key ),
			[ $this, 'admin_page_display' ]
		);

		$this->options_page = add_menu_page(
			$translatedTitle,
			$translatedTitle,
			'manage_options',
			$this->key,
			[ $this, 'admin_page_display' ]
		);
		remove_menu_page( $this->key );
		// Include CMB CSS in the head to avoid FOUC
		add_action( "admin_print_styles-{$this->options_page}", [ 'CMB2_hookup', 'enqueue_cmb_css' ] );
	}

	/**
	 * Admin page markup. Mostly handled by CMB2
	 * @since  0.1.0
	 */
	public function admin_page_display() {
		?>
        <div class="wrap cmb2-options-page <?php
		echo $this->key; ?>">
            <h2><?php
				echo esc_html( get_admin_page_title() ); ?></h2>
			<?php
			cmb2_metabox_form( $this->metabox_id, $this->key ); ?>
        </div>
		<?php
	}

	/**
	 * Add the options metabox to the array of metaboxes
	 * @since  0.1.0
	 */
	public function add_options_page_metabox() {
		// hook in our save notices
		add_action( "cmb2_save_options-page_fields_{$this->metabox_id}", [ $this, 'settings_notices' ], 10, 2 );

		$cmb = new_cmb2_box(
			[
				'id'         => $this->metabox_id,
				'hookup'     => false,
				'cmb_styles' => true,
				'show_on'    => [
					// These are important, don't remove
					'key'   => 'options-page',
					'value' => [ $this->key, ],
				],
			]
		);

		#
		# MAIL
		#
		$cmb->add_field(
			[
				'name'       => __( 'New member email settings:', 'simpleshop-cz' ),
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
				'type'       => 'title',
				'id'         => 'ssc_email_title',
			]
		);
		$cmb->add_field(
			[
				'name'             => __( 'Send an email to a new member?', 'simpleshop-cz' ),
				'id'               => 'ssc_email_enable',
				'type'             => 'select',
				'show_option_none' => false,
				'classes_cb'       => [ $this, 'hide_when_invalid_keys' ],
				'default'          => '1',
				'options'          => [
					'1' => __( 'Yes, send an email to the new member.', 'simpleshop-cz' ),
					'2' => __( 'No, don\'t send an email to the new member.', 'simpleshop-cz' ),
				],
			]
		);
		$cmb->add_field(
			[
				'name'       => __( 'Email subject', 'simpleshop-cz' ),
				'id'         => 'ssc_email_subject',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
				'type'       => 'text',
				'default'    => __( 'You have been granted access to the member section', 'simpleshop-cz' ),
			]
		);


		$cmb->add_field(
			[
				'name'       => __( 'Email message', 'simpleshop-cz' ),
				'desc'       => __( '<u>Allowed patterns:</u><br/>'
				                    . '<div style="font-style:normal;"><b>{login}</b> = login<br/>'
				                    . '<b>{password}</b> = password<br/>'
				                    . '<b>{login_url}</b> = URL address where User can login<br/>'
				                    . '<b>{pages}</b> = list of pages to which the user has purchased access<br/>'
				                    . '<b>{mail}</b> = user email (usually the same as login)<br/>'
				                    . '</div>'
					,
					'simpleshop-cz' ),
				'id'         => 'ssc_email_text',
				'type'       => 'wysiwyg',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
				'default'    => sprintf( __( 'Dear customer,
you have been granted access to the member section.

Login: {login}
Password: {password}

You can sign in at: %s

Your purchased content:
{pages}

With regards,
SimpleShop.cz - <i>Everyone can sell with us</i>'
					,
					'simpleshop-cz' ),
					wp_login_url() ),
			]
		);


		#
		# API
		#
		$cmb->add_field(
			[
				'name' => __( 'API settings – connection with the SimpleShop application:', 'simpleshop-cz' ),
				'type' => 'title',
				'id'   => 'ssc_api_title',
			]
		);

		// Set our CMB2 fields
		$cmb->add_field(
			[
				'name' => __( 'Username (email)', 'simpleshop-cz' ),
				'desc' => __( 'Enter the email address used for login to SimpleShop', 'simpleshop-cz' ),
				'id'   => 'ssc_api_email',
				'type' => 'text',
			]
		);

		$cmb->add_field(
			[
				'name' => __( 'SimpleShop API Key', 'simpleshop-cz' ),
				'desc' => __( 'The key can be found in SimpleShop -> Settings -> Connection -> WordPress/Mioweb',
					'simpleshop-cz' ),
				'id'   => 'ssc_api_key',
				'type' => 'text',
			]
		);

		$cmb->add_field(
			[
				'name'       => __( 'SimpleShop API Endpoint URL', 'simpleshop-cz' ),
				'desc'       => __( '[SERVICE FLAG] You can here override URL to SimpleShop API. Leave blank to use default API.',
					'simpleshop-cz' ),
				'id'         => 'ssc_api_endpoint_url',
				'type'       => 'text',
				'classes_cb' => [ $this, 'show_debug_fields' ],
			]
		);

		$cmb->add_field(
			[
				'name'       => __( 'Simplehop Form base URL', 'simpleshop-cz' ),
				'desc'       => __( '[SERVICE FLAG] Base URL to SimpleShop form URL. Leave blank to use default URL.',
					'simpleshop-cz' ),
				'id'         => 'ssc_ss_form_url',
				'type'       => 'text',
				'classes_cb' => [ $this, 'show_debug_fields' ],
			]
		);

		$cmb->add_field(
			[
				'name'       => __( 'General settings', 'simpleshop-cz' ),
				'type'       => 'title',
				'id'         => 'ssc_general_settings_title',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
			]
		);

		$cmb->add_field(
			[
				'name'       => __( 'Redirect after login', 'simpleshop-cz' ),
				'type'       => 'text',
				'id'         => 'ssc_redirect_url',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
			]
		);
		$cmb->add_field(
			[
				'name'       => __( 'Remove secured items from RSS', 'simpleshop-cz' ),
				'type'       => 'checkbox',
				'id'         => 'ssc_hide_from_rss',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
			]
		);


		$cmb->add_field(
			[
				'name'       => __( 'Disconnect', 'simpleshop-cz' ),
				'type'       => 'title',
				'id'         => 'ssc_remove_api_title',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
			]
		);

		$cmb->add_field(
			[
				'name'       => __( 'Disconnect SimpleShop', 'simpleshop-cz' ),
				'desc'       => __( 'You found it at SimpleShop in Settings (Nastavení) -> WP Plugin',
					'simpleshop-cz' ),
				'id'         => 'ssc_api_disconnect',
				'type'       => 'disconnect_button',
				'classes_cb' => [ $this, 'hide_when_invalid_keys' ],
			]
		);
	}

	/**
	 * Maybe delete the API keys
	 */
	public function maybe_disconnect_simpleshop() {
		if ( ! wp_verify_nonce( $_GET['_wpnonce'] ) ) {
			return;
		}

		if ( ! isset( $_GET['disconnect_simpleshop'] ) || $_GET['disconnect_simpleshop'] !== '1' ) {
			return;
		}

		// Unset only API keys, leave the other settings saved
		$options = get_option( $this->key );
		unset( $options['ssc_api_email'] );
		unset( $options['ssc_api_key'] );

		// Set valid API keys to false
		update_option( 'ssc_valid_api_keys', 0 );

		// Update the SS options
		update_option( $this->key, $options );
	}

	/**
	 * Register settings notices for display
	 *
	 * @param int   $object_id Option key
	 * @param array $updated   Array of updated fields
	 *
	 * @return void
	 * @since  0.1.0
	 *
	 */
	public function settings_notices( $object_id, $updated ) {
		$api_email = $this->loader->get_api_email();
		$api_key   = $this->loader->get_api_key();

		if ( ! $api_email && isset( $_POST['ssc_api_email'] ) ) {
			$api_email = sanitize_email( $_POST['ssc_api_email'] );
		}

		if ( ! $api_key && isset( $_POST['ssc_api_key'] ) ) {
			$api_key = sanitize_text_field( $_POST['ssc_api_key'] );
		}

		$vyfakturuj_api = $this->loader->get_api_client( $api_email, $api_key );
		try {
			$result = $this->loader->init_plugin_activation( $vyfakturuj_api );
			if ( isset( $result['status'] ) && $result['status'] === 'success' ) {
				update_option( 'ssc_valid_api_keys', 1 );
			} else {
				update_option( 'ssc_valid_api_keys', 0 );
			}
		} catch ( VyfakturujAPIException $e ) {
			update_option( 'ssc_valid_api_keys', 0 );

			add_settings_error( $this->key . '-error',
				'',
				__( 'Error during communication with SimpleShop API, please try it later', 'simpleshop-cz' )
			);
			settings_errors( $this->key . '-error' );

			return;
		}


		if ( $object_id !== $this->key || empty( $updated ) ) {
			return;
		}

		add_settings_error( $this->key . '-notices', '', __( 'Settings updated.', 'simpleshop-cz' ), 'updated' );
		settings_errors( $this->key . '-notices' );
	}

	/**
	 * Check, if we already got valid API key, if not, add 'hidden' class to the settings that are not needed in the first step
	 * We switched to this approach, because by just hiding the fields the default values are saved even on the first save,
	 * but previously the fields were removed completely from the form, so the default values were not saved until the API keys were in place
	 * @return array
	 */
	public function hide_when_invalid_keys() {
		// If the keys are valid, do nothing
		if ( get_option( 'ssc_valid_api_keys' ) == 1 ) {
			return [];
		}

		return [ 'hidden' ];
	}

	public function show_debug_fields() {
		if ( isset( $_GET['debug'] ) ) {
			return [];
		}

		return [ 'hidden' ];
	}

	/**
	 * Public getter method for retrieving protected/private variables
	 *
	 * @param string $field Field to retrieve
	 *
	 * @return mixed          Field value or exception is thrown
	 * @throws Exception
	 * @since  0.1.0
	 *
	 */
	public function __get( $field ) {
		// Allowed fields to retrieve
		if ( in_array( $field, [ 'key', 'metabox_id', 'title', 'options_page' ], true ) ) {
			return $this->{$field};
		}

		throw new Exception( 'Invalid property: ' . $field );
	}

	/**
	 * Wrapper function around cmb2_get_option
	 *
	 * @param string $key     Options array key
	 * @param mixed  $default Optional default value
	 *
	 * @return mixed           Option value
	 * @since  0.1.0
	 *
	 */
	public function ssc_get_option( $key = '', $default = null ) {
		if ( function_exists( 'cmb2_get_option' ) ) {
			// Use cmb2_get_option as it passes through some key filters.
			return cmb2_get_option( $this->key, $key, $default );
		}

		// Fallback to get_option if CMB2 is not loaded yet.
		$opts = get_option( $this->key, $key );

		$val = $default;

		if ( 'all' == $key ) {
			$val = $opts;
		} elseif ( is_array( $opts ) && array_key_exists( $key, $opts ) && false !== $opts[ $key ] ) {
			$val = $opts[ $key ];
		}

		return $val;
	}

	public function is_settings_page() {
		return is_admin() && ! empty( $_GET['page'] ) && 'ssc_options' === $_GET['page'];
	}

	public function maybe_display_messages() {
		if ( ! empty( $_POST['object_id'] ) ) {
			if ( ! empty( $_POST['ssc_api_endpoint_url'] ) ) {
				add_action( 'admin_notices', [ $this, 'custom_api_endpoint_notice' ] );
			}
		} else {
			if ( $this->ssc_get_option( 'ssc_api_endpoint_url' ) ) {
				add_action( 'admin_notices', [ $this, 'custom_api_endpoint_notice' ] );
			}
		}
	}

	public function custom_api_endpoint_notice() {
		$url = empty( $_POST['ssc_api_endpoint_url'] ) ? $this->ssc_get_option( 'ssc_api_endpoint_url' ) : esc_attr( $_POST['ssc_api_endpoint_url'] );
		?>
        <div class="notice notice-warning">
            <p><?php
				printf( __( "Warning: You have set custom SimpleShop API Endpoint URL: '%s'", 'simpleshop-cz' ),
					$url ); ?></p>
        </div>
		<?php
	}
}
