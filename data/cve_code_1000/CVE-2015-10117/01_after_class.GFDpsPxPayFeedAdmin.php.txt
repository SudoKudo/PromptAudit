<?php

/**
* Feed admin
*/
class GFDpsPxPayFeedAdmin {

	protected $plugin;							// handle to the plugin object

	/**
	* @param GFDpsPxPayPlugin $plugin handle to the plugin object
	*/
	public function __construct($plugin) {
		$this->plugin = $plugin;

		add_filter('wp_print_scripts', array($this, 'removeScripts'));
		add_filter('parent_file', array($this, 'filterParentFile'));
		add_filter('views_edit-'.GFDPSPXPAY_TYPE_FEED, array($this, 'filterViewsEdit'));
		add_action('add_meta_boxes_'.GFDPSPXPAY_TYPE_FEED, array($this, 'actionAddMetaBoxes'));
		add_action('save_post', array($this, 'saveCustomFields'), 10, 2);
		add_filter('manage_'.GFDPSPXPAY_TYPE_FEED.'_posts_columns', array($this, 'filterManageColumns'));
		add_filter('post_row_actions', array($this, 'filterPostRowActions'), 10, 2);
		add_filter('wp_insert_post_data', array($this, 'filterInsertPostData'), 10, 2);
		add_filter('post_updated_messages', array($this, 'filterPostUpdatedMessages'));
		add_filter('parse_query', array($this, 'adminPostOrder'));

		$min = defined('SCRIPT_DEBUG') && SCRIPT_DEBUG ? '' : '.min';
		$ver = defined('SCRIPT_DEBUG') && SCRIPT_DEBUG ? time() : GFDPSPXPAY_PLUGIN_VERSION;
		wp_enqueue_script('gfdpspxpay-feed-admin', "{$this->plugin->urlBase}js/feed-admin$min.js", array('jquery'), $ver, true);
	}

	/**
	* remove some scripts we don't want loaded
	*/
	public function removeScripts() {
		// stop WordPress SEO breaking our tooltips!
		wp_dequeue_script('wp-seo-metabox');
		wp_dequeue_script('jquery-qtip');
	}

	/**
	* tell WordPress admin that Gravity Forms menu is parent page
	* @param string $parent_file
	* @return string
	*/
	public function filterParentFile($parent_file) {
		global $submenu_file;

		// set parent menu for filter return
		$parent_file = 'gf_edit_forms';

		// set submenu by side effect
		$submenu_file = 'gfdpspxpay-feeds';

		return $parent_file;
	}

	/**
	* remove views we don't need from post list
	* @param array $views
	* @return array
	*/
	public function filterViewsEdit($views) {
		unset($views['publish']);
		unset($views['draft']);

		return $views;
	}

	/**
	* add meta boxes for custom fields
	* @param WP_Post $post
	*/
	public function actionAddMetaBoxes($post) {
		try {
			$feed = new GFDpsPxPayFeed();
			if ($post && $post->ID) {
				$feed->loadFromPost($post);
			}
		}
		catch (GFDpsPxPayException $e) {
			// NOP -- we'll have an empty feed
		}

		add_meta_box('meta_'.GFDPSPXPAY_TYPE_FEED.'_form', 'Gravity Form', array($this, 'metaboxForm'),
			GFDPSPXPAY_TYPE_FEED, 'normal', 'high', array('feed' => $feed));
		add_meta_box('meta_'.GFDPSPXPAY_TYPE_FEED.'_fields', 'Map Form to Transaction', array($this, 'metaboxFields'),
			GFDPSPXPAY_TYPE_FEED, 'normal', 'high', array('feed' => $feed));
		add_meta_box('meta_'.GFDPSPXPAY_TYPE_FEED.'_urls', 'Redirect URLs', array($this, 'metaboxURLs'),
			GFDPSPXPAY_TYPE_FEED, 'normal', 'high', array('feed' => $feed));
		add_meta_box('meta_'.GFDPSPXPAY_TYPE_FEED.'_opts', 'Options', array($this, 'metaboxOpts'),
			GFDPSPXPAY_TYPE_FEED, 'normal', 'high', array('feed' => $feed));
		add_meta_box('meta_'.GFDPSPXPAY_TYPE_FEED.'_list', 'Return to List', array($this, 'metaboxList'),
			GFDPSPXPAY_TYPE_FEED, 'side', 'low', array('feed' => $feed));

		// replace standard Publish box with a custom one
		remove_meta_box('submitdiv', GFDPSPXPAY_TYPE_FEED, 'side');
		add_meta_box('meta_'.GFDPSPXPAY_TYPE_FEED.'_submit', 'Save', array($this, 'metaboxSave'),
			GFDPSPXPAY_TYPE_FEED, 'side', 'high', array('feed' => $feed));
	}

	/**
	* metabox for Return to List link
	* @param WP_Post $post
	* @param array $metabox has metabox id, title, callback, and args elements.
	*/
	public function metaboxList($post, $metabox) {
		$feedsURL = admin_url('edit.php?post_type=' . GFDPSPXPAY_TYPE_FEED);
		printf('<a href="%s">Click to return to list</a>', esc_url($feedsURL));
	}

	/**
	* metabox for custom save/publish
	* @param WP_Post $post
	* @param array $metabox has metabox id, title, callback, and args elements.
	*/
	public function metaboxSave($post, $metabox) {
		global $action;

		include GFDPSPXPAY_PLUGIN_ROOT . 'views/metabox-save.php';
	}

	/**
	* metabox for Gravity Form field, only listing forms that don't have a feed or are current feed's form
	* @param WP_Post $post
	* @param array $metabox has metabox id, title, callback, and args elements.
	*/
	public function metaboxForm($post, $metabox) {
		$feed = $metabox['args']['feed'];
		$forms = GFFormsModel::get_forms();

		$feeds = GFDpsPxPayFeed::getList();
		$feedMap = array();
		foreach ($feeds as $f) {
			$feedMap[$f->FormID] = 1;
		}

		include GFDPSPXPAY_PLUGIN_ROOT . 'views/metabox-form.php';
	}

	/**
	* metabox for Redirect URLs
	* @param WP_Post $post
	* @param array $metabox has metabox id, title, callback, and args elements.
	*/
	public function metaboxURLs($post, $metabox) {
		$feed = $metabox['args']['feed'];

		include GFDPSPXPAY_PLUGIN_ROOT . 'views/metabox-urls.php';
	}

	/**
	* metabox for options
	* @param WP_Post $post
	* @param array $metabox has metabox id, title, callback, and args elements.
	*/
	public function metaboxOpts($post, $metabox) {
		$feed = $metabox['args']['feed'];

		include GFDPSPXPAY_PLUGIN_ROOT . 'views/metabox-options.php';
	}

	/**
	* metabox for Fields to Map
	* @param WP_Post $post
	* @param array $metabox has metabox id, title, callback, and args elements.
	*/
	public function metaboxFields($post, $metabox) {
		wp_nonce_field('save', GFDPSPXPAY_TYPE_FEED.'_wpnonce', false);

		$feed = $metabox['args']['feed'];
		$fields = $feed->FormID ? self::getFormFields($feed->FormID) : false;

		include GFDPSPXPAY_PLUGIN_ROOT . 'views/metabox-fields.php';
	}

	/**
	* filter insert fields, to set post title from form name
	* @param array $data the post insert data
	* @param array $postarr data from the form post
	* @return array
	*/
	public function filterInsertPostData($data, $postarr) {
		$formID = isset($postarr['_gfdpspxpay_form']) ? intval($postarr['_gfdpspxpay_form']) : 0;
		if ($formID) {
			$form = GFFormsModel::get_form($formID);
			$data['post_title'] = $form->title;
			$data['post_name'] = sanitize_title($form->title);
		}

		return $data;
	}

	/**
	* save custom fields
	*/
	public function saveCustomFields($postID) {
		// Check whether this is an auto save routine. If it is, our form has not been submitted, so we don't want to do anything
		if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE)
			return $postID;

		global $typenow;

		// handle post type
		if ($typenow == GFDPSPXPAY_TYPE_FEED) {
			// verify permission to edit post / page
			if (!current_user_can('edit_post', $postID))
				return $postID;

			$fields = array (
				'_gfdpspxpay_form',
				'_gfdpspxpay_url_fail',
				'_gfdpspxpay_url_success',
				'_gfdpspxpay_merchant_ref',
				'_gfdpspxpay_email',
				'_gfdpspxpay_txndata1',
				'_gfdpspxpay_txndata2',
				'_gfdpspxpay_txndata3',
				'_gfdpspxpay_opt',
				'_gfdpspxpay_delay_post',
				'_gfdpspxpay_delay_notify',
				'_gfdpspxpay_delay_autorespond',
				'_gfdpspxpay_delay_userrego',
				'_gfdpspxpay_delay_exec_always',
			);

			if (isset($_POST['_gfdpspxpay_form'])) {
				check_admin_referer('save', GFDPSPXPAY_TYPE_FEED . '_wpnonce');
			}

			foreach ($fields as $fieldName) {
				if (isset($_POST[$fieldName])) {

					$value = $_POST[$fieldName];

					if (empty($value)) {
						delete_post_meta($postID, $fieldName);
					}
					else {
						update_post_meta($postID, $fieldName, $value);
					}
				}
				else {
					// checkboxes aren't set, so delete them
					delete_post_meta($postID, $fieldName);
				}
			}
		}

		return $postID;
	}

	/**
	* remove unwanted actions from list of feeds
	* @param array $actions
	* @param WP_Post $post
	* @return array
	*/
	public function filterPostRowActions($actions, $post) {
		unset($actions['inline hide-if-no-js']);		// "quick edit"

		// add Entries link
		if ($post && $post->ID) {
			try {
				$feed = new GFDpsPxPayFeed();
				$feed->loadFromPost($post);

				$delete = array_pop($actions);		// pop the end link, so that we can "insert" ours before it

				$url = add_query_arg(array('page' => 'gf_entries', 'id' => $feed->FormID), admin_url('admin.php'));
				$actions['entries'] = sprintf('<a href="%s" title="%s">%s</a>', esc_url($url), 'View Entries', 'Entries');

				$actions['delete'] = $delete;		// replace the end link
			}
			catch (GFDpsPxPayException $e) {
				// NOP -- we'll have an empty feed
			}
		}

		return $actions;
	}

	/**
	* change the post updated messages
	* @param array $messages
	* @return array
	*/
	public function filterPostUpdatedMessages($messages) {
		$messages[GFDPSPXPAY_TYPE_FEED] = array(
			 0 => '', // Unused. Messages start at index 1.
			 1 => 'Feed updated.',
			 2 => 'Custom field updated.',
			 3 => 'Custom field deleted.',
			 4 => 'Feed updated.',
			/* translators: %s: date and time of the revision */
			 5 => isset($_GET['revision']) ? sprintf( 'Feed restored to revision from %s', wp_post_revision_title( (int) $_GET['revision'], false ) ) : false,
			 6 => 'Feed published.',
			 7 => 'Feed saved.',
			 8 => 'Feed submitted.',
			 9 => 'Feed scheduled for: ',
			10 => 'Feed draft updated.',
		);

		return $messages;
	}

	/**
	* filter to add columns to post list
	* @param array $posts_columns
	* @return array
	*/
	public function filterManageColumns($posts_columns) {
		// Date isn't useful for this post type
		unset($posts_columns['date']);

		// stop File Gallery adding No. of Attachments
		unset($posts_columns['attachment_count']);

		return $posts_columns;
	}

	/**
	* change default order to name ascending
	* @param WP_Query $query
	* @return WP_Query
	*/
	public function adminPostOrder($query) {
		// only for admin queries for this post type, with no specified order
		if ($query->is_admin && $query->get('post_type') == GFDPSPXPAY_TYPE_FEED && empty($query->query_vars['orderby'])) {
			$query->set('orderby', 'post_title');
			$query->set('order', 'ASC');
		}

		return $query;
	}

	/**
	* get a map of GF form field IDs to field names, for populating drop-down lists
	* @param int $formID
	* @return array
	*/
	public static function getFormFields($formID) {
		$form = GFFormsModel::get_form_meta($formID);

        $fields = array(
        	'form' => $formID . ' (form ID)',
        	'title' => $form['title'] . ' (form title)',
        );

        if (is_array($form['fields'])) {
            foreach ($form['fields'] as $field) {
                if (!rgar($field, 'displayOnly')) {
					// pick up simple fields and selected compound fields
					if (empty($field['inputs']) || in_array(GFFormsModel::get_input_type($field), array('name', 'address'))) {
						$fields[(string) $field['id']] = GFCommon::get_label($field);
					}

					// pick up subfields
					if (isset($field['inputs']) && is_array($field['inputs'])) {
						foreach($field['inputs'] as $input) {
							$fields[(string) $input['id']] = GFCommon::get_label($field, $input['id']);
						}
					}
				}
            }
        }

        return $fields;
	}

	/**
	* return a list of drop-down list items for field mappings
	* @param string $current the currently selected option
	* @param array $fields
	* @return string
	*/
	public static function selectFields($current, $fields) {
		$opts = '<option value="">-- not selected --</option>';

		foreach ($fields as $name => $title) {
			$opts .= sprintf('<option value="%s" %s>%s</option>', esc_attr($name), selected($current, $name, false), esc_html($title));
		}

		return $opts;
	}

}
