<?php
/*
Plugin Name: Contact Form Plugin
Plugin URI:  http://bestwebsoft.com/plugin/
Description: Plugin for Contact Form.
Author: BestWebSoft
Version: 3.21
Author URI: http://bestwebsoft.com/
License: GPLv2 or later
*/
/*  Copyright 2011  BestWebSoft  ( plugin@bestwebsoft.com )

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License, version 2, as 
    published by the Free Software Foundation.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

if( ! function_exists( 'bws_add_menu_render' ) ) {
	function bws_add_menu_render() {
		global $title;
		$active_plugins = get_option('active_plugins');
		$all_plugins		= get_plugins();

		$array_activate = array();
		$array_install	= array();
		$array_recomend = array();
		$count_activate = $count_install = $count_recomend = 0;
		$array_plugins	= array(
			array( 'captcha\/captcha.php', 'Captcha', 'http://wordpress.org/extend/plugins/captcha/', 'http://bestwebsoft.com/plugin/captcha-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Captcha+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=captcha.php' ), 
			array( 'contact-form-plugin\/contact_form.php', 'Contact Form', 'http://wordpress.org/extend/plugins/contact-form-plugin/', 'http://bestwebsoft.com/plugin/contact-form/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Contact+Form+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=contact_form.php' ), 
			array( 'facebook-button-plugin\/facebook-button-plugin.php', 'Facebook Like Button Plugin', 'http://wordpress.org/extend/plugins/facebook-button-plugin/', 'http://bestwebsoft.com/plugin/facebook-like-button-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Facebook+Like+Button+Plugin+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=facebook-button-plugin.php' ), 
			array( 'twitter-plugin\/twitter.php', 'Twitter Plugin', 'http://wordpress.org/extend/plugins/twitter-plugin/', 'http://bestwebsoft.com/plugin/twitter-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Twitter+Plugin+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=twitter.php' ), 
			array( 'portfolio\/portfolio.php', 'Portfolio', 'http://wordpress.org/extend/plugins/portfolio/', 'http://bestwebsoft.com/plugin/portfolio-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Portfolio+bestwebsoft&plugin-search-input=Search+Plugins', '' ),
			array( 'gallery-plugin\/gallery-plugin.php', 'Gallery', 'http://wordpress.org/extend/plugins/gallery-plugin/', 'http://bestwebsoft.com/plugin/gallery-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Gallery+Plugin+bestwebsoft&plugin-search-input=Search+Plugins', '' ),
			array( 'adsense-plugin\/adsense-plugin.php', 'Google AdSense Plugin', 'http://wordpress.org/extend/plugins/adsense-plugin/', 'http://bestwebsoft.com/plugin/google-adsense-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Adsense+Plugin+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=adsense-plugin.php' ),
			array( 'custom-search-plugin\/custom-search-plugin.php', 'Custom Search Plugin', 'http://wordpress.org/extend/plugins/custom-search-plugin/', 'http://bestwebsoft.com/plugin/custom-search-plugin/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Custom+Search+plugin+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=custom_search.php' ),
			array( 'quotes_and_tips\/quotes-and-tips.php', 'Quotes and Tips', 'http://wordpress.org/extend/plugins/quotes-and-tips/', 'http://bestwebsoft.com/plugin/quotes-and-tips/', '/wp-admin/plugin-install.php?tab=search&type=term&s=Quotes+and+Tips+bestwebsoft&plugin-search-input=Search+Plugins', 'admin.php?page=quotes-and-tips.php' )
		);
		foreach($array_plugins as $plugins) {
			if( 0 < count( preg_grep( "/".$plugins[0]."/", $active_plugins ) ) ) {
				$array_activate[$count_activate]['title'] = $plugins[1];
				$array_activate[$count_activate]['link']	= $plugins[2];
				$array_activate[$count_activate]['href']	= $plugins[3];
				$array_activate[$count_activate]['url']	= $plugins[5];
				$count_activate++;
			}
			else if( array_key_exists(str_replace("\\", "", $plugins[0]), $all_plugins) ) {
				$array_install[$count_install]['title'] = $plugins[1];
				$array_install[$count_install]['link']	= $plugins[2];
				$array_install[$count_install]['href']	= $plugins[3];
				$count_install++;
			}
			else {
				$array_recomend[$count_recomend]['title'] = $plugins[1];
				$array_recomend[$count_recomend]['link']	= $plugins[2];
				$array_recomend[$count_recomend]['href']	= $plugins[3];
				$array_recomend[$count_recomend]['slug']	= $plugins[4];
				$count_recomend++;
			}
		}
		?>
		<div class="wrap">
			<div class="icon32 icon32-bws" id="icon-options-general"></div>
			<h2><?php echo $title;?></h2>
			<?php if( 0 < $count_activate ) { ?>
			<div>
				<h3><?php _e( 'Activated plugins', 'contact_form' ); ?></h3>
				<?php foreach( $array_activate as $activate_plugin ) { ?>
				<div style="float:left; width:200px;"><?php echo $activate_plugin['title']; ?></div> <p><a href="<?php echo $activate_plugin['link']; ?>" target="_blank"><?php echo __( "Read more", 'contact_form'); ?></a> <a href="<?php echo $activate_plugin['url']; ?>"><?php echo __( "Settings", 'contact_form'); ?></a></p>
				<?php } ?>
			</div>
			<?php } ?>
			<?php if( 0 < $count_install ) { ?>
			<div>
				<h3><?php _e( 'Installed plugins', 'contact_form' ); ?></h3>
				<?php foreach($array_install as $install_plugin) { ?>
				<div style="float:left; width:200px;"><?php echo $install_plugin['title']; ?></div> <p><a href="<?php echo $install_plugin['link']; ?>" target="_blank"><?php echo __( "Read more", 'contact_form'); ?></a></p>
				<?php } ?>
			</div>
			<?php } ?>
			<?php if( 0 < $count_recomend ) { ?>
			<div>
				<h3><?php _e( 'Recommended plugins', 'contact_form' ); ?></h3>
				<?php foreach( $array_recomend as $recomend_plugin ) { ?>
				<div style="float:left; width:200px;"><?php echo $recomend_plugin['title']; ?></div> <p><a href="<?php echo $recomend_plugin['link']; ?>" target="_blank"><?php echo __( "Read more", 'contact_form'); ?></a> <a href="<?php echo $recomend_plugin['href']; ?>" target="_blank"><?php echo __( "Download", 'contact_form'); ?></a> <a class="install-now" href="<?php echo get_bloginfo( "url" ) . $recomend_plugin['slug']; ?>" title="<?php esc_attr( sprintf( __( 'Install %s' ), $recomend_plugin['title'] ) ) ?>" target="_blank"><?php echo __( 'Install now from wordpress.org', 'contact_form' ) ?></a></p>
				<?php } ?>
				<span style="color: rgb(136, 136, 136); font-size: 10px;"><?php _e( 'If you have any questions, please contact us via plugin@bestwebsoft.com or fill in our contact form on our site', 'contact_form' ); ?> <a href="http://bestwebsoft.com/contact/">http://bestwebsoft.com/contact/</a></span>
			</div>
			<?php } ?>
		</div>
		<?php
	}
}

// Add option page in admin menu
if( ! function_exists( 'cntctfrm_admin_menu' ) ) {
	function cntctfrm_admin_menu() {
		add_menu_page( 'BWS Plugins', 'BWS Plugins', 'edit_themes', 'bws_plugins', 'bws_add_menu_render', plugins_url( "images/px.png", __FILE__ ), 1001); 
		add_submenu_page('bws_plugins', __( 'Contact Form Options', 'contact_form' ), __( 'Contact Form', 'contact_form' ), 'edit_themes', "contact_form.php", 'cntctfrm_settings_page');

		//call register settings function
		add_action( 'admin_init', 'cntctfrm_settings' );
	}
}

// Register settings for plugin
if( ! function_exists( 'cntctfrm_settings' ) ) {
	function cntctfrm_settings() {
		global $cntctfrm_options;

		$cntctfrm_option_defaults = array(
			'cntctfrm_user_email' => 'admin',
			'cntctfrm_custom_email' => '',
			'cntctfrm_select_email' => 'user',
			'cntctfrm_additions_options' => 0,
			'cntctfrm_attachment' => 0,
			'cntctfrm_attachment_explanations' => 1,
			'cntctfrm_send_copy' => 0,
			'cntctfrm_from_field' => get_bloginfo( 'name' ),
			'cntctfrm_display_add_info' => 1,
			'cntctfrm_display_sent_from' => 1,
			'cntctfrm_display_date_time' => 1,
			'cntctfrm_mail_method' => 'wp-mail',
			'cntctfrm_display_coming_from' => 1,
			'cntctfrm_display_user_agent' => 1,
			'cntctfrm_change_label' => 0,
			'cntctfrm_name_label' => __( "Name:", 'contact_form' ),
			'cntctfrm_email_label' => __( "E-Mail Address:", 'contact_form' ),
			'cntctfrm_subject_label' => __( "Subject:", 'contact_form' ),
			'cntctfrm_message_label' => __( "Message:", 'contact_form' ),
			'cntctfrm_attachment_label' => __( "Attachment:", 'contact_form' ),
			'cntctfrm_action_after_send' => 1,
			'cntctfrm_thank_text' => __( "Thank you for contacting us.", 'contact_form' ),
			'cntctfrm_redirect_url' => ''
		);
		if( ! get_option( 'cntctfrm_options' ) )
			add_option( 'cntctfrm_options', $cntctfrm_option_defaults, '', 'yes' );

		$cntctfrm_options = get_option( 'cntctfrm_options' );
		$cntctfrm_options = array_merge( $cntctfrm_option_defaults, $cntctfrm_options );
		update_option( 'cntctfrm_options', $cntctfrm_options );
	}
}

// Add settings page in admin area
if( ! function_exists( 'cntctfrm_settings_page' ) ) {
	function cntctfrm_settings_page() {
		global $cntctfrm_options, $wpdb;

		$userslogin = $wpdb->get_col( "SELECT user_login FROM  $wpdb->users ", 0 ); 

		$error = "";	
		// Save data for settings page
		if( isset( $_REQUEST['cntctfrm_form_submit'] ) ) {
			$cntctfrm_options_submit['cntctfrm_user_email'] = $_REQUEST['cntctfrm_user_email'];
			$cntctfrm_options_submit['cntctfrm_custom_email'] = $_REQUEST['cntctfrm_custom_email'];
			$cntctfrm_options_submit['cntctfrm_select_email'] = $_REQUEST['cntctfrm_select_email'];
			$cntctfrm_options_submit['cntctfrm_additions_options'] = isset( $_REQUEST['cntctfrm_additions_options']) ? $_REQUEST['cntctfrm_additions_options'] : 0;
			if($cntctfrm_options_submit['cntctfrm_additions_options'] == 0) {
				$cntctfrm_options_submit['cntctfrm_attachment']					= 0;
				$cntctfrm_options_submit['cntctfrm_attachment_explanations']					= 1;
				$cntctfrm_options_submit['cntctfrm_send_copy']					= 0;
				$cntctfrm_options_submit['cntctfrm_from_field']					= get_bloginfo( 'name' );
				$cntctfrm_options_submit['cntctfrm_display_add_info']		= 1;
				$cntctfrm_options_submit['cntctfrm_display_sent_from']	= 1;
				$cntctfrm_options_submit['cntctfrm_display_date_time']	= 1;
				$cntctfrm_options_submit['cntctfrm_mail_method']				= 'wp-mail';
				$cntctfrm_options_submit['cntctfrm_display_coming_from'] = 1;
				$cntctfrm_options_submit['cntctfrm_display_user_agent'] = 1;
				$cntctfrm_options_submit['cntctfrm_change_label']				= 0;
				$cntctfrm_options_submit['cntctfrm_name_label']					= __( "Name:", 'contact_form' );
				$cntctfrm_options_submit['cntctfrm_email_label']				= __( "E-Mail Address:", 'contact_form' );
				$cntctfrm_options_submit['cntctfrm_subject_label']			= __( "Subject:", 'contact_form' );
				$cntctfrm_options_submit['cntctfrm_message_label']			= __( "Message:", 'contact_form' );
				$cntctfrm_options_submit['cntctfrm_attachment_label']		= __( "Attachment:", 'contact_form' );
				$cntctfrm_options_submit['cntctfrm_action_after_send']	= 1;
			 $cntctfrm_options_submit['cntctfrm_thank_text']	= __( "Thank you for contacting us.", 'contact_form' );
			 $cntctfrm_options_submit['cntctfrm_redirect_url']	= '';
			} else {
				$cntctfrm_options_submit['cntctfrm_attachment']				= isset( $_REQUEST['cntctfrm_attachment']) ? $_REQUEST['cntctfrm_attachment'] : 0;
				$cntctfrm_options_submit['cntctfrm_attachment_explanations']				= isset( $_REQUEST['cntctfrm_attachment_explanations']) ? $_REQUEST['cntctfrm_attachment_explanations'] : 0;
				$cntctfrm_options_submit['cntctfrm_send_copy']				= isset( $_REQUEST['cntctfrm_send_copy']) ? $_REQUEST['cntctfrm_send_copy'] : 0;
				$cntctfrm_options_submit['cntctfrm_mail_method']			= $_REQUEST['cntctfrm_mail_method'];
				$cntctfrm_options_submit['cntctfrm_from_field']				= $_REQUEST['cntctfrm_from_field'];
				$cntctfrm_options_submit['cntctfrm_display_add_info'] = isset( $_REQUEST['cntctfrm_display_add_info']) ? 1 : 0;
				$cntctfrm_options_submit['cntctfrm_change_label']			= isset( $_REQUEST['cntctfrm_change_label']) ? 1 : 0;
				if( $cntctfrm_options_submit['cntctfrm_display_add_info'] == 1 ) {
					$cntctfrm_options_submit['cntctfrm_display_sent_from']		= isset( $_REQUEST['cntctfrm_display_sent_from']) ? 1 : 0;
					$cntctfrm_options_submit['cntctfrm_display_date_time']		= isset( $_REQUEST['cntctfrm_display_date_time']) ? 1 : 0;
					$cntctfrm_options_submit['cntctfrm_display_coming_from']	= isset( $_REQUEST['cntctfrm_display_coming_from']) ? 1 : 0;
					$cntctfrm_options_submit['cntctfrm_display_user_agent']		= isset( $_REQUEST['cntctfrm_display_user_agent']) ? 1 : 0;
				}
				else {
					$cntctfrm_options_submit['cntctfrm_display_sent_from']		= 1;
					$cntctfrm_options_submit['cntctfrm_display_date_time']		= 1;
					$cntctfrm_options_submit['cntctfrm_display_coming_from']	= 1;
					$cntctfrm_options_submit['cntctfrm_display_user_agent']		= 1;
				}
				if( $cntctfrm_options_submit['cntctfrm_change_label'] == 1 ) {
					$cntctfrm_options_submit['cntctfrm_name_label']				= isset( $_REQUEST['cntctfrm_name_label']) ? $_REQUEST['cntctfrm_name_label'] : $cntctfrm_options_submit['cntctfrm_name_label'];
					$cntctfrm_options_submit['cntctfrm_email_label']			= isset( $_REQUEST['cntctfrm_email_label']) ? $_REQUEST['cntctfrm_email_label'] : $cntctfrm_options_submit['cntctfrm_email_label'];
					$cntctfrm_options_submit['cntctfrm_subject_label']		= isset( $_REQUEST['cntctfrm_subject_label']) ? $_REQUEST['cntctfrm_subject_label'] : $cntctfrm_options_submit['cntctfrm_subject_label'];
					$cntctfrm_options_submit['cntctfrm_message_label']		= isset( $_REQUEST['cntctfrm_message_label']) ? $_REQUEST['cntctfrm_message_label'] : $cntctfrm_options_submit['cntctfrm_message_label'];
					$cntctfrm_options_submit['cntctfrm_attachment_label'] = isset( $_REQUEST['cntctfrm_attachment_label']) ? $_REQUEST['cntctfrm_attachment_label'] : $cntctfrm_options_submit['cntctfrm_attachment_label'];
				}
				else {
					$cntctfrm_options_submit['cntctfrm_name_label']				= __( "Name:", 'contact_form' );
					$cntctfrm_options_submit['cntctfrm_email_label']			= __( "E-Mail Address:", 'contact_form' );
					$cntctfrm_options_submit['cntctfrm_subject_label']		= __( "Subject:", 'contact_form' );
					$cntctfrm_options_submit['cntctfrm_message_label']		= __( "Message:", 'contact_form' );
					$cntctfrm_options_submit['cntctfrm_attachment_label'] = __( "Attachment:", 'contact_form' );
				}
				$cntctfrm_options_submit['cntctfrm_action_after_send']	= $_REQUEST['cntctfrm_action_after_send'];
			 $cntctfrm_options_submit['cntctfrm_thank_text']	= $_REQUEST['cntctfrm_thank_text'];
			 $cntctfrm_options_submit['cntctfrm_redirect_url']	= $_REQUEST['cntctfrm_redirect_url'];
			}			
			$cntctfrm_options = array_merge( $cntctfrm_options, $cntctfrm_options_submit  );
			if( $cntctfrm_options_submit['cntctfrm_action_after_send'] == 0 
				&& ( trim( $cntctfrm_options_submit['cntctfrm_redirect_url'] ) == "" 
				|| !preg_match( '@^(?:http://)?([^/]+)@i', trim( $cntctfrm_options_submit['cntctfrm_redirect_url'] ) ) ) ) {
					$error .=__(  "If the option 'Redirect to page' is selected then url field should be fillied in the following format", 'contact_form' )." <code>http://your_site/your_page</code>";
					$cntctfrm_options['cntctfrm_action_after_send'] = 1;
			}
			if( 'user' == $cntctfrm_options_submit['cntctfrm_select_email'] ) {
				if( function_exists('get_userdatabylogin') && false !== get_userdatabylogin( $cntctfrm_options_submit['cntctfrm_user_email'] ) )
				{
					update_option( 'cntctfrm_options', $cntctfrm_options, '', 'yes' );
					$message = __( "Options saved.", 'contact_form' );
				}
				else if( false !== get_user_by( 'login', $cntctfrm_options_submit['cntctfrm_user_email'] ) )
				{
					update_option( 'cntctfrm_options', $cntctfrm_options, '', 'yes' );
					$message = __( "Options saved.", 'contact_form' );
				}
				else {
					$error .=__(  "Such user is not exist. Settings are not saved.", 'contact_form' );
				}
			}
			else {
				if( $cntctfrm_options_submit['cntctfrm_custom_email']  != "" && preg_match( "/^((?:[a-z0-9]+(?:[a-z0-9\-_\.]+)?@[a-z0-9]+(?:[a-z0-9\-\.]+)?\.[a-z]{2,5})[, ]*)+$/i", trim( $cntctfrm_options_submit['cntctfrm_custom_email'] ) ) ) {
					update_option( 'cntctfrm_options', $cntctfrm_options, '', 'yes' );
					$message = __( "Options saved.", 'contact_form' );
				}
				else {
					$error .= __( "Please input correct email. Settings are not saved.", 'contact_form' );
				}
			}
		}
		// Display form on the setting page
	?>
	<div class="wrap">
		<div class="icon32 icon32-bws" id="icon-options-general"></div>
		<h2><?php _e( "Contact Form Options", 'contact_form' ); ?></h2>
		<div class="updated fade" <?php if( ! isset( $_REQUEST['cntctfrm_form_submit'] ) || $error != "" ) echo "style=\"display:none\""; ?>><p><strong><?php echo $message; ?></strong></p></div>
		<div class="error" <?php if( "" == $error ) echo "style=\"display:none\""; ?>><p><strong><?php echo $error; ?></strong></p></div>
		<form method="post" action="admin.php?page=contact_form.php">
			<span style="margin-bottom:15px;">
				<p><?php _e( "If you would like to add a Contact Form to your website, just copy and put this shortcode onto your post or page or widget:", 'contact_form' ); ?> [contact_form]</p>
				<?php _e( "If information in the below fields are empty then the message will be send to an address which was specified during registration.", 'contact_form' ); ?>
			</span>
			<table class="form-table">
				<tr valign="top">
					<th scope="row" style="width:195px;"><?php _e( "Use email of wordpress user:", 'contact_form' ); ?> </th>
					<td style="width:15px;">
						<input type="radio" id="cntctfrm_select_email_user" name="cntctfrm_select_email" value="user" <?php if($cntctfrm_options['cntctfrm_select_email'] == 'user') echo "checked=\"checked\" "; ?>/>
					</td>
					<td>
						<select name="cntctfrm_user_email">
							<option disabled><?php _e( "Select user name", 'contact_form' ); ?></option>
							<?php while( list( $key, $value ) = each( $userslogin ) ) { ?>
								<option value="<?php echo $value; ?>" <?php if( $cntctfrm_options['cntctfrm_user_email'] == $value ) echo "selected=\"selected\" "; ?>><?php echo $value; ?></option>
							<?php } ?>
						</select>
						<span class="cntctfrm_info"><?php _e( "Set a name of user who will get messages from a contact form.", 'contact_form' ); ?></span>
					</td>
				</tr>
				<tr valign="top">
					<th scope="row" style="width:195px;"><?php _e( "Use this email:", 'contact_form' ); ?> </th>
					<td>
						<input type="radio" id="cntctfrm_select_email_custom" name="cntctfrm_select_email" value="custom" <?php if($cntctfrm_options['cntctfrm_select_email'] == 'custom') echo "checked=\"checked\" "; ?>/>
					</td>
					<td>
						<input type="text" name="cntctfrm_custom_email" value="<?php echo $cntctfrm_options['cntctfrm_custom_email']; ?>" onfocus="document.getElementById('cntctfrm_select_email_custom').checked = true;" />
						<span class="cntctfrm_info"><?php _e( "Set an email address which will be used for messages receiving.", 'contact_form' ); ?></span>
					</td>
				</tr>
				<tr valign="top">
					<th colspan="3" scope="row" style="width:195px;"><input type="checkbox" id="cntctfrm_additions_options" name="cntctfrm_additions_options" value="1" <?php if($cntctfrm_options['cntctfrm_additions_options'] == '1') echo "checked=\"checked\" "; ?> /> <?php _e( "Additional options", 'contact_form' ); ?></th>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Display Attachment block", 'contact_form' ); ?></th>
					<td>
						<input type="checkbox" id="cntctfrm_attachment" name="cntctfrm_attachment" value="1" <?php if($cntctfrm_options['cntctfrm_attachment'] == '1') echo "checked=\"checked\" "; ?>/>
					</td>
					<td>
						<span  class="cntctfrm_info"><?php echo __( "Users can attach files of the following types", 'contact_form' ) . ": html, txt, css, gif, png, jpeg, jpg, tiff, bmp, ai, eps, ps, rtf, pdf, doc, docx, zip, rar, wav, mp3, ppt"; ?></span>
					</td>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Display Attachment explanations", 'contact_form' ); ?></th>
					<td>
						<input type="checkbox" id="cntctfrm_attachment_explanations" name="cntctfrm_attachment_explanations" value="1" <?php if( $cntctfrm_options['cntctfrm_attachment_explanations'] == '1' && $cntctfrm_options['cntctfrm_attachment'] == '1' ) echo "checked=\"checked\" "; ?>/>
					</td>
					<td>
						<span  class="cntctfrm_info"><?php echo __( "Display explanations after Attachment block", 'contact_form' ); ?></span>
					</td>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if( $cntctfrm_options['cntctfrm_additions_options'] == '0' ) echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Display Send me a copy block", 'contact_form' ); ?></th>
					<td colspan="2">
						<input type="checkbox" id="cntctfrm_send_copy" name="cntctfrm_send_copy" value="1" <?php if($cntctfrm_options['cntctfrm_send_copy'] == '1') echo "checked=\"checked\" "; ?>/>
					</td>
				</tr>
				<tr class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th rowspan="2"><?php _e( 'What use?', 'contact_form' ); ?></th>
					<td>
						<input type='radio' name='cntctfrm_mail_method' value='wp-mail' <?php if( $cntctfrm_options['cntctfrm_mail_method'] == 'wp-mail' ) echo "checked=\"checked\" "; ?>/>
					</td>
					<td>
						<?php _e( 'Wp-mail', 'mail-send' ); ?> 
						<span  class="cntctfrm_info">(<?php _e( 'To send mail you can use the wordpress wp_mail function', 'mail_send' ); ?>)</span>
					</td>
				</tr>
				<tr class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<td>
						<input type='radio' name='cntctfrm_mail_method' value='mail' <?php if($cntctfrm_options['cntctfrm_mail_method'] == 'mail') echo "checked=\"checked\" "; ?>/>
					</td>
					<td>
						<?php _e( 'Mail', 'mail-send' ); ?> 
						<span  class="cntctfrm_info">(<?php _e( 'To send mail you can use the php mail function', 'mail_send' ); ?>)</span>
					</td>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Change FROM fields of the contact form", 'contact_form' ); ?></th>
					<td colspan="2">
						<input type="text" style="width:200px;" name="cntctfrm_from_field" value="<?php echo stripslashes( $cntctfrm_options['cntctfrm_from_field'] ); ?>" /><br />
					</td>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Display additional info in email", 'contact_form' ); ?></th>
					<td>
						<input type="checkbox" id="cntctfrm_display_add_info" name="cntctfrm_display_add_info" value="1" <?php if($cntctfrm_options['cntctfrm_display_add_info'] == '1') echo "checked=\"checked\" "; ?>/>
					</td>
					<td class="cntctfrm_display_add_info_block <?php if($cntctfrm_options['cntctfrm_display_add_info'] == '0') echo "cntctfrm_hidden"; ?>">
						<input type="checkbox" id="cntctfrm_display_sent_from" name="cntctfrm_display_sent_from" value="1" <?php if($cntctfrm_options['cntctfrm_display_sent_from'] == '1') echo "checked=\"checked\" "; ?>/> <span class="cntctfrm_info"><?php _e( "Sent from (ip address)", 'contact_form' ); ?></span><br />
						<input type="checkbox" id="cntctfrm_display_date_time" name="cntctfrm_display_date_time" value="1" <?php if($cntctfrm_options['cntctfrm_display_date_time'] == '1') echo "checked=\"checked\" "; ?>/> <span class="cntctfrm_info"><?php _e( "Date/Time", 'contact_form' ); ?></span><br />
						<input type="checkbox" id="cntctfrm_display_coming_from" name="cntctfrm_display_coming_from" value="1" <?php if($cntctfrm_options['cntctfrm_display_coming_from'] == '1') echo "checked=\"checked\" "; ?>/> <span class="cntctfrm_info"><?php _e( "Coming from (referer)", 'contact_form' ); ?></span><br />
						<input type="checkbox" id="cntctfrm_display_user_agent" name="cntctfrm_display_user_agent" value="1" <?php if($cntctfrm_options['cntctfrm_display_user_agent'] == '1') echo "checked=\"checked\" "; ?>/> <span class="cntctfrm_info"><?php _e( "Using (user agent)", 'contact_form' ); ?></span><br />
					</td>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Change label for fields of the contact form", 'contact_form' ); ?></th>
					<td>
						<input type="checkbox" id="cntctfrm_change_label" name="cntctfrm_change_label" value="1" <?php if($cntctfrm_options['cntctfrm_change_label'] == '1') echo "checked=\"checked\" "; ?>/>
					</td>
					<td class="cntctfrm_change_label_block <?php if($cntctfrm_options['cntctfrm_change_label'] == '0') echo "cntctfrm_hidden"; ?>">
						<input type="text" name="cntctfrm_name_label" value="<?php echo $cntctfrm_options['cntctfrm_name_label']; ?>" /> <span class="cntctfrm_info"><?php _e( "Name:", 'contact_form' ); ?></span><br />
						<input type="text" name="cntctfrm_email_label" value="<?php echo $cntctfrm_options['cntctfrm_email_label']; ?>" /> <span class="cntctfrm_info"><?php _e( "E-Mail Address:", 'contact_form' ); ?></span><br />
						<input type="text" name="cntctfrm_subject_label" value="<?php echo $cntctfrm_options['cntctfrm_subject_label']; ?>" /> <span class="cntctfrm_info"><?php _e( "Subject:", 'contact_form' ); ?></span><br />
						<input type="text" name="cntctfrm_message_label" value="<?php echo $cntctfrm_options['cntctfrm_message_label']; ?>" /> <span class="cntctfrm_info"><?php _e( "Message:", 'contact_form' ); ?></span><br />
						<input type="text" name="cntctfrm_attachment_label" value="<?php echo $cntctfrm_options['cntctfrm_attachment_label']; ?>" /> <span class="cntctfrm_info"><?php _e( "Attachment:", 'contact_form' ); ?></span><br />
					</td>
				</tr>
				<tr valign="top" class="cntctfrm_additions_block <?php if($cntctfrm_options['cntctfrm_additions_options'] == '0') echo "cntctfrm_hidden"; ?>">
					<th scope="row" style="width:195px;"><?php _e( "Action after the send mail", 'contact_form' ); ?></th>
					<td colspan="2" class="cntctfrm_action_after_send_block">
					 <input type="radio" id="cntctfrm_action_after_send" name="cntctfrm_action_after_send" value="1" <?php if($cntctfrm_options['cntctfrm_action_after_send'] == '1') echo "checked=\"checked\" "; ?>/> <span class="cntctfrm_info"><?php _e( "Display text", 'contact_form' ); ?></span><br />
						<input type="text" name="cntctfrm_thank_text" value="<?php echo $cntctfrm_options['cntctfrm_thank_text']; ?>" /> <span class="cntctfrm_info"><?php _e( "Text", 'contact_form' ); ?></span><br />
						<input type="radio" id="cntctfrm_action_after_send" name="cntctfrm_action_after_send" value="0" <?php if($cntctfrm_options['cntctfrm_action_after_send'] == '0') echo "checked=\"checked\" "; ?>/> <span class="cntctfrm_info"><?php _e( "Redirect to page", 'contact_form' ); ?></span><br />
						<input type="text" name="cntctfrm_redirect_url" value="<?php echo $cntctfrm_options['cntctfrm_redirect_url']; ?>" /> <span class="cntctfrm_info"><?php _e( "Url", 'contact_form' ); ?></span><br />
					</td>
			</table>    
			<input type="hidden" name="cntctfrm_form_submit" value="submit" />
			<p class="submit">
				<input type="submit" class="button-primary" value="<?php _e('Save Changes') ?>" />
			</p>
		</form>
	</div>
	<?php 
	}
}

// Display contact form in front end - page or post
if( ! function_exists( 'cntctfrm_display_form' ) ) {
	function cntctfrm_display_form() {
		global $error_message, $cntctfrm_options, $result;
		$cntctfrm_options = get_option( 'cntctfrm_options' );
		$content = "";

		$page_url = ( isset( $_SERVER["HTTPS"] ) && $_SERVER["HTTPS"] == "on" ? "https://" : "http://" ).$_SERVER["SERVER_NAME"].$_SERVER["REQUEST_URI"];
		// If contact form submited
		$name = isset( $_REQUEST['cntctfrm_contact_name'] ) ? $_REQUEST['cntctfrm_contact_name'] : "";
		$email = isset( $_REQUEST['cntctfrm_contact_email'] ) ? $_REQUEST['cntctfrm_contact_email'] : "";
		$subject = isset( $_REQUEST['cntctfrm_contact_subject'] ) ? $_REQUEST['cntctfrm_contact_subject'] : "";
		$message = isset( $_REQUEST['cntctfrm_contact_message'] ) ? $_REQUEST['cntctfrm_contact_message'] : "";
		$send_copy = isset( $_REQUEST['cntctfrm_contact_send_copy'] ) ? $_REQUEST['cntctfrm_contact_send_copy'] : "";
		// If it is good
		if( true === $result ) {
			$_SESSION['cntctfrm_send_mail'] = true;
			if( $cntctfrm_options['cntctfrm_action_after_send'] == 1 )
				$content .= $cntctfrm_options['cntctfrm_thank_text'];
			else
				$content .= "<script type='text/javascript'>window.location.href = '".$cntctfrm_options['cntctfrm_redirect_url']."';</script>";
		}
		else if( false === $result )
		{
			// If email not be delivered
			$error_message['error_form'] = __( "Sorry, your e-mail could not be delivered.", 'contact_form' );
		}
		else { 
			$_SESSION['cntctfrm_send_mail'] = false;
			// Output form
			$content .= '<form method="post" id="cntctfrm_contact_form" action="'.$page_url.'" enctype="multipart/form-data">';
			if( isset( $error_message['error_form'] ) ) { 
				$content .= '<div style="text-align: left; color: red;">'.$error_message['error_form'].'</div>';
				}
			$content .= '<div style="text-align: left; padding-top: 5px;">
					<label for="cntctfrm_contact_name">'. $cntctfrm_options['cntctfrm_name_label'] . '<span class="required"> *</span></label>
				</div>';
			if( isset( $error_message['error_name'] ) ) {
				$content .= '<div style="text-align: left; color: red;">'.$error_message['error_name'].'</div>';
			}
			$content .= '<div style="text-align: left;">
					<input class="text" type="text" size="40" value="'.$name.'" name="cntctfrm_contact_name" id="cntctfrm_contact_name" style="text-align: left; margin: 0;" />
				</div>

				<div style="text-align: left;">
					<label for="cntctfrm_contact_email">'. $cntctfrm_options['cntctfrm_email_label'] . '<span class="required"> *</span></label>
				</div>';
			if( isset( $error_message['error_email'] ) ) {
				$content .= '<div style="text-align: left; color: red;">'.$error_message['error_email'].'</div>';
				}
			$content .= '<div style="text-align: left;">
					<input class="text" type="text" size="40" value="'.$email.'" name="cntctfrm_contact_email" id="cntctfrm_contact_email" style="text-align: left; margin: 0;" />
				</div>

				<div style="text-align: left;">
					<label for="cntctfrm_contact_subject">'. $cntctfrm_options['cntctfrm_subject_label'] . '<span class="required"> *</span></label>
				</div>';
			if( isset( $error_message['error_subject'] ) ) {
				$content .= '<div style="text-align: left; color: red;">'.$error_message['error_subject'].'</div>';
			}
			$content .= '<div style="text-align: left;">
					<input class="text" type="text" size="40" value="'.$subject.'" name="cntctfrm_contact_subject" id="cntctfrm_contact_subject" style="text-align: left; margin: 0;" />
				</div>

				<div style="text-align: left;">
					<label for="cntctfrm_contact_message">'. $cntctfrm_options['cntctfrm_message_label'] . '<span class="required"> *</span></label>
				</div>';
			if( isset( $error_message['error_message'] ) ) {
				$content .= '<div style="text-align: left; color: red;">'.$error_message['error_message'].'</div>';
			}
			$content .= '<div style="text-align: left;">
					<textarea rows="5" cols="30" name="cntctfrm_contact_message" id="cntctfrm_contact_message">'.$message.'</textarea>
				</div>';
			if($cntctfrm_options['cntctfrm_attachment'] == 1 ) {
				$content .= '<div style="text-align: left;">
						<label for="cntctfrm_contact_attachment">'. $cntctfrm_options['cntctfrm_attachment_label'] . '</label>
					</div>';
				if( isset( $error_message['error_attachment'] ) ) {
					$content .= '<div style="text-align: left; color: red;">'.$error_message['error_attachment'].'</div>';
				}
				$content .= '<div style="text-align: left;">
						<input type="file" name="cntctfrm_contact_attachment" id="cntctfrm_contact_attachment"'.(isset( $error_message['error_attachment'] ) ? "class='error'": "").' />';
				if( $cntctfrm_options['cntctfrm_attachment_explanations'] == 1 ){
						$content .= '<label style="font-size:10px;"><br />'. __( "You can attach files of the following types", 'contact_form' ) . ': html, txt, css, gif, png, jpeg, jpg, tiff, bmp, ai, eps, ps, rtf, pdf, doc, docx, zip, rar, wav, mp3, ppt</label>';
				}
				$content .= '
				</div>';
			}
			if($cntctfrm_options['cntctfrm_send_copy'] == 1 ) {
				$content .= '<div style="text-align: left;">
						<input type="checkbox" value="1" name="cntctfrm_contact_send_copy" id="cntctfrm_contact_send_copy" style="text-align: left; margin: 0;" '.( $send_copy == '1' ? " checked=\"checked\" " : "" ).' />
						<label for="cntctfrm_contact_send_copy">'. __( "Send me a copy", 'contact_form' ). '</label>
					</div>';
			}

			if(has_filter('cntctfrm_display_captcha')) {
				$content .= apply_filters( 'cntctfrm_display_captcha' , $error_message );
			}
				
			$content .= '<div style="text-align: left; padding-top: 8px;">
					<input type="hidden" value="send" name="cntctfrm_contact_action"><input type="hidden" value="Version: 3.13" />
					<input type="submit" value="'. __( "Submit", 'contact_form' ). '" style="cursor: pointer; margin: 0pt; text-align: center;margin-bottom:10px;" /> 
				</div>
				</form>';
		}
		return $content ;
	}
}

if( ! function_exists( 'cntctfrm_check_and_send' ) ) {
		function cntctfrm_check_and_send() {
				global $result;
				$cntctfrm_options = get_option( 'cntctfrm_options' );
				if( isset( $_REQUEST['cntctfrm_contact_action'] ) )
				{
					// Check all input data
					$result = cntctfrm_check_form();
				}
				// If it is good
				if( true === $result ) {
					$_SESSION['cntctfrm_send_mail'] = true;
					if( $cntctfrm_options['cntctfrm_action_after_send'] == 0 ){
						wp_redirect( $cntctfrm_options['cntctfrm_redirect_url'] ); 
						exit;
					}
				}
		}
}

// Check all input data
if( ! function_exists( 'cntctfrm_check_form' ) ) {
	function cntctfrm_check_form() {
		global $error_message;
		global $cntctfrm_options;
		$path_of_uploaded_file = '';
		if( empty( $cntctfrm_options ) )
				$cntctfrm_options = get_option( 'cntctfrm_options' );
		$result = "";
		// Error messages array
		$error_message = array();
		$error_message['error_name'] = __( "Your name is required.", 'contact_form' );
		$error_message['error_email'] = __( "A proper e-mail address is required.", 'contact_form' );
		$error_message['error_subject'] = __( "Subject text is required.", 'contact_form' );
		$error_message['error_message'] = __( "Message text is required.", 'contact_form' );
		$error_message['error_form'] = __( "Please make corrections below and try again.", 'contact_form' );
		if( $cntctfrm_options['cntctfrm_attachment'] == 1 ) {
			global $path_of_uploaded_file;
			global $mime_type;
			$mime_type= array(
				'html'=>'text/html', 
				'htm'=>'text/html', 
				'txt'=>'text/plain', 
				'css'=>'text/css', 
				'gif'=>'image/gif',
				'png'=>'image/x-png',
				'jpeg'=>'image/jpeg',
				'jpg'=>'image/jpeg',
				'JPG'=>'image/jpeg',
				'jpe'=>'image/jpeg',
				'TIFF'=>'image/tiff',
				'tiff'=>'image/tiff',
				'tif'=>'image/tiff',
				'bmp'=>'image/x-ms-bmp',
				'ai'=>'application/postscript',
				'eps'=>'application/postscript',
				'ps'=>'application/postscript',
				'rtf'=>'application/rtf',
				'pdf'=>'application/pdf',
				'doc'=>'application/msword',
				'docx'=>'application/mswor',
				'zip'=>'application/zip',
				'rar'=>'application/rar',
				'wav'=>'audio/wav',
				'mp3'=>'audio/mp3',
				'ppt'=>'application/vnd.ms-powerpoint');
			$error_message['error_attachment'] = __( "Attachment is broken.", "contact_form" );
		}
		// Check information wich was input in fields
		if( "" != $_REQUEST['cntctfrm_contact_name'] )
			unset( $error_message['error_name'] );
		if( "" != $_REQUEST['cntctfrm_contact_email'] && preg_match( "/^(?:[a-z0-9]+(?:[a-z0-9\-_\.]+)?@[a-z0-9]+(?:[a-z0-9\-\.]+)?\.[a-z]{2,5})$/i", trim( $_REQUEST['cntctfrm_contact_email'] ) ) )
			unset( $error_message['error_email'] );
		if( "" != $_REQUEST['cntctfrm_contact_subject'] )
			unset( $error_message['error_subject'] );
		if( "" != $_REQUEST['cntctfrm_contact_message'] )
			unset( $error_message['error_message'] );
		// If captcha plugin exists
		if( ! apply_filters( 'cntctfrm_check_form', $_REQUEST ) )
			$error_message['error_captcha'] = __( "Please complete the CAPTCHA.", 'contact_form' );
		if( isset($_FILES["cntctfrm_contact_attachment"]["tmp_name"]) && $_FILES["cntctfrm_contact_attachment"]["tmp_name"] != "") {
			if( is_multisite() ){
				if( defined('UPLOADS') ) {
					if( ! is_dir( ABSPATH . UPLOADS ) ) {
						wp_mkdir_p( ABSPATH . UPLOADS );
					}
					$path_of_uploaded_file = ABSPATH . UPLOADS. $_FILES["cntctfrm_contact_attachment"]["name"];
				}
				else if ( defined( 'BLOGUPLOADDIR' ) ) {
					if( ! is_dir( BLOGUPLOADDIR ) ) {
						wp_mkdir_p( BLOGUPLOADDIR );
					}
					$path_of_uploaded_file = BLOGUPLOADDIR. $_FILES["cntctfrm_contact_attachment"]["name"];
				}
			}
			else {
				$uploads = wp_upload_dir();
				if( ! isset( $uploads['path'] ) && isset ( $uploads['error'] ) )
						$error_message['error_attachment'] = $uploads['error'];
				else
						$path_of_uploaded_file = $uploads['path'] ."/". $_FILES["cntctfrm_contact_attachment"]["name"];
			}
			$tmp_path = $_FILES["cntctfrm_contact_attachment"]["tmp_name"];
			$path_info = pathinfo( $path_of_uploaded_file );

			if( array_key_exists ($path_info['extension'], $mime_type) ) {
				if( is_uploaded_file( $tmp_path ) ) {
					if( copy( $tmp_path, $path_of_uploaded_file ) ) {
						unset( $error_message['error_attachment'] );
					}
				}
			}
		} else {
			unset( $error_message['error_attachment'] );
		}
		if( 1 == count( $error_message ) ) {
			unset( $error_message['error_form'] );
			// If all is good - send mail
			$result = cntctfrm_send_mail();
		}
		return $result;
	}
}

// Send mail function
if( ! function_exists( 'cntctfrm_send_mail' ) ) {
	function cntctfrm_send_mail() {
		global $cntctfrm_options, $path_of_uploaded_file;
		$to = "";
		if( isset( $_SESSION['cntctfrm_send_mail'] ) && $_SESSION['cntctfrm_send_mail'] == true )
			return true;
		if($cntctfrm_options['cntctfrm_select_email'] == 'user') {
				if( function_exists('get_userdatabylogin') && false !== $user = get_userdatabylogin($cntctfrm_options['cntctfrm_user_email'] ) ){
					$to = $user->user_email;
				}
				else if( false !== $user = get_user_by( 'login', $cntctfrm_options_submit['cntctfrm_user_email'] ) )
						$to = $user->user_email;
		}
		else {
			$to = $cntctfrm_options['cntctfrm_custom_email'];
		}
		if( "" == $to ) {
			// If email options are not certain choose admin email
			$to = get_option("admin_email");
		}
		if( "" != $to ) {
			// subject
			$subject = $_REQUEST['cntctfrm_contact_subject'];
			$user_info_string = '';
			$userdomain = '';
			$form_action_url = '';
			$attachments = array();
			$headers  = "";

			if ( getenv('HTTPS') == 'on' ) {
				$form_action_url = 'https://'.$_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI'];
			} else {
				$form_action_url = 'http://'.$_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI'];
			}

			if( $cntctfrm_options['cntctfrm_display_add_info'] == 1) {
				$userdomain = gethostbyaddr($_SERVER['REMOTE_ADDR']);
				if( $cntctfrm_options['cntctfrm_display_add_info'] == 1 ||
						$cntctfrm_options['cntctfrm_display_sent_from'] == 1 ||
						$cntctfrm_options['cntctfrm_display_coming_from'] == 1 ||
						$cntctfrm_options['cntctfrm_display_user_agent'] == 1 ) {
					$user_info_string .= '<tr>
							<td><br /></td><td><br /></td>
						</tr>';
				}
				if( $cntctfrm_options['cntctfrm_display_sent_from'] == 1) {
					$user_info_string .= '<tr>
							<td>'.__('Sent from (ip address)', 'contact_form').':</td><td>'.$_SERVER['REMOTE_ADDR']." ( ". $userdomain ." )".'</td>
						</tr>';
				}
				if( $cntctfrm_options['cntctfrm_display_date_time'] == 1) {
					$user_info_string .= '<tr>
							<td>'.__('Date/Time', 'contact_form').':</td><td>'.date_i18n( get_option( 'date_format' ).' '.get_option( 'time_format' ), strtotime( current_time( 'mysql' ) ) ).'</td>
						</tr>';
				}
				if( $cntctfrm_options['cntctfrm_display_coming_from'] == 1) {
					$user_info_string .= '<tr>
							<td>'.__('Coming from (referer)', 'contact_form').':</td><td>'.$form_action_url.'</td>
						</tr>';
				}
				if( $cntctfrm_options['cntctfrm_display_user_agent'] == 1) {
					$user_info_string .= '<tr>
							<td>'.__('Using (user agent)', 'contact_form').':</td><td>'.cntctfrm_clean_input($_SERVER['HTTP_USER_AGENT']).'</td>
						</tr>';
				}
			}
			// message
			$message = '
			<html>
			<head>
				<title>'. __( "Contact from", 'contact_form' ) . get_bloginfo('name').'</title>
			</head>
			<body>
				<table>
					<tr>
						<td width="160">'. __( "Name", 'contact_form' ) . '</td><td>'.$_REQUEST['cntctfrm_contact_name'].'</td>
					</tr>
					<tr>
						<td>'. __( "Email", 'contact_form' ) .'</td><td>'.$_REQUEST['cntctfrm_contact_email'].'</td>
					</tr>
					<tr>
						<td>'. __( "Subject", 'contact_form' ) . '</td><td>'.$_REQUEST['cntctfrm_contact_subject'].'</td>
					</tr>
					<tr>
						<td>'. __( "Message", 'contact_form' ) . '</td><td>'.$_REQUEST['cntctfrm_contact_message'].'</td>
					</tr>
					<tr>
						<td>'. __( "Site", 'contact_form' ) . '</td><td>'.get_bloginfo("url").'</td>
					</tr>
					<tr>
						<td><br /></td><td><br /></td>
					</tr>
					'.$user_info_string.'
				</table>
			</body>
			</html>
			';
			if( $cntctfrm_options['cntctfrm_mail_method'] == 'wp-mail' ){
				// To send HTML mail, the Content-type header must be set
				$headers  = 'MIME-Version: 1.0' . "\r\n";
				$headers .= 'Content-type: text/html; charset=utf-8' . "\r\n";

				// Additional headers
				$headers .= 'From: '.$_REQUEST['cntctfrm_contact_email']. "\r\n";
				if( $cntctfrm_options['cntctfrm_attachment'] == 1 && isset($_FILES["cntctfrm_contact_attachment"]["tmp_name"]) && $_FILES["cntctfrm_contact_attachment"]["tmp_name"] != "") {
					$attachments = array( $path_of_uploaded_file );
				}

				if( isset( $_REQUEST['cntctfrm_contact_send_copy'] ) && $_REQUEST['cntctfrm_contact_send_copy'] == 1 )
					wp_mail($_REQUEST['cntctfrm_contact_email'], stripslashes($subject), stripslashes($message), $headers, $attachments);

				// Mail it
				return wp_mail($to, stripslashes($subject), stripslashes($message), $headers, $attachments);
			}
			else{
				if( $cntctfrm_options['cntctfrm_attachment'] == 1 && isset($_FILES["cntctfrm_contact_attachment"]["tmp_name"]) && $_FILES["cntctfrm_contact_attachment"]["tmp_name"] != "") {
					global $path_of_uploaded_file;
					$headers  = "";
					$message_block = $message;

					// Additional headers
					$headers .= 'From: '.$_REQUEST['cntctfrm_contact_email']. "\r\n";

					$bound_text = 	"jimmyP123";
		 
					$bound = 	"--".$bound_text."\r\n";

					$bound_last = 	"--".$bound_text."--\r\n";

					$headers .= "MIME-Version: 1.0\r\n"
						."Content-Type: multipart/mixed; boundary=\"$bound_text\"";

					$message = 	__( "If you can see this MIME than your client doesn't accept MIME types!", "contact_form" ) . "\r\n"
						.$bound;

		 
					$message .= 	"Content-Type: text/html; charset=\"utf-8\"\r\n"
							."Content-Transfer-Encoding: 7bit\r\n\r\n"
						."".$message_block."\r\n"
						.$bound;
		 
					$file = 	file_get_contents($path_of_uploaded_file);
					$path_info = pathinfo( $path_of_uploaded_file );
					 
					$message .= 	"Content-Type: ".$path_info['extension']."; name=\"".basename($path_of_uploaded_file)."\"\r\n"
							."Content-Transfer-Encoding: base64\r\n"
							."Content-disposition: attachment; file=\"".basename($path_of_uploaded_file)."\"\r\n"
							."\r\n"
							.chunk_split( base64_encode( $file ) )
							.$bound_last;
				}
				else {
					// To send HTML mail, the Content-type header must be set
					$headers  = 'MIME-Version: 1.0' . "\r\n";
					$headers .= 'Content-type: text/html; charset=utf-8' . "\r\n";

					// Additional headers
					$headers .= 'From: '.$_REQUEST['cntctfrm_contact_email']. "\r\n";
				}
				if( isset( $_REQUEST['cntctfrm_contact_send_copy'] ) && $_REQUEST['cntctfrm_contact_send_copy'] == 1 )
					@mail($_REQUEST['cntctfrm_contact_email'], stripslashes($subject), stripslashes($message), $headers);

				return @mail($to, stripslashes($subject), stripslashes($message), $headers);
			}
			
		}
		return false;
	}
}

function cntctfrm_plugin_action_links( $links, $file ) {
		//Static so we don't call plugin_basename on every plugin row.
	static $this_plugin;
	if ( ! $this_plugin ) $this_plugin = plugin_basename(__FILE__);

	if ( $file == $this_plugin ){
			 $settings_link = '<a href="admin.php?page=contact_form.php">' . __('Settings', 'contact_form') . '</a>';
			 array_unshift( $links, $settings_link );
		}
	return $links;
} // end function cntctfrm_plugin_action_links

function cntctfrm_register_plugin_links($links, $file) {
	$base = plugin_basename(__FILE__);
	if ($file == $base) {
		$links[] = '<a href="admin.php?page=contact_form.php">' . __('Settings','contact_form') . '</a>';
		$links[] = '<a href="http://wordpress.org/extend/plugins/contact-form-plugin/faq/" target="_blank">' . __('FAQ','contact_form') . '</a>';
		$links[] = '<a href="Mailto:plugin@bestwebsoft.com">' . __('Support','contact_form') . '</a>';
	}
	return $links;
}

function cntctfrm_clean_input($string, $preserve_space = 0) {
	if ( is_string( $string ) ) {
		if($preserve_space) {
			return cntctfrm_sanitize_string( strip_tags( stripslashes( $string ) ), $preserve_space );
		}
		return trim( cntctfrm_sanitize_string( strip_tags( stripslashes( $string ) ) ) );
	} 
	else if ( is_array( $string ) ) {
		reset( $string );
		while ( list($key, $value ) = each( $string ) ) {
			$string[$key] = cntctfrm_clean_input($value,$preserve_space);
		}
		return $string;
	} 
	else {
		return $string;
	}
} // end function ctf_clean_input

// functions for protecting and validating form vars
function cntctfrm_sanitize_string($string, $preserve_space = 0 ) {
	if( ! $preserve_space )
		$string = preg_replace("/ +/", ' ', trim( $string ) );

	return preg_replace( "/[<>]/", '_', $string );
}

//Function '_plugin_init' are using to add language files.
if ( ! function_exists ( 'cntctfrm_plugin_init' ) ) {
	function cntctfrm_plugin_init() {
		if ( ! session_id() )
			session_start();
		load_plugin_textdomain( 'contact_form', false, dirname( plugin_basename( __FILE__ ) ) . '/languages/' ); 
	}
} // end function cntctfrm_plugin_init


if ( ! function_exists ( 'cntctfrm_admin_head' ) ) {
	function cntctfrm_admin_head() {
		wp_enqueue_style( 'cntctfrmStylesheet', plugins_url( 'css/style.css', __FILE__ ) );
		wp_enqueue_script( 'cntctfrmScript', plugins_url( 'js/script.js', __FILE__ ) );
	}
}

if ( ! function_exists ( 'cntctfrm_wp_head' ) ) {
	function cntctfrm_wp_head() {
		wp_enqueue_style( 'cntctfrmStylesheet', plugins_url( 'css/style.css', __FILE__ ) );
	}
}

function cntctfrm_email_name_filter( $data ){
	global $cntctfrm_options;
	if( isset( $cntctfrm_options['cntctfrm_from_field'] ) && trim( $cntctfrm_options['cntctfrm_from_field'] ) != "" )
		return stripslashes( $cntctfrm_options['cntctfrm_from_field'] );
	else
		return $data;
}

add_action( 'init', 'cntctfrm_plugin_init' );

add_action( 'init', 'cntctfrm_check_and_send' );

add_action( 'admin_enqueue_scripts', 'cntctfrm_admin_head' );

add_action( 'wp_enqueue_scripts', 'cntctfrm_wp_head' );

// adds "Settings" link to the plugin action page
add_filter( 'plugin_action_links', 'cntctfrm_plugin_action_links',10,2);

//Additional links on the plugin page
add_filter( 'plugin_row_meta', 'cntctfrm_register_plugin_links',10,2);

add_shortcode( 'contact_form', 'cntctfrm_display_form' );

add_action( 'admin_menu', 'cntctfrm_admin_menu' );

add_filter( 'widget_text', 'do_shortcode' );

add_filter( 'wp_mail_from_name', 'cntctfrm_email_name_filter', 10, 1);
?>