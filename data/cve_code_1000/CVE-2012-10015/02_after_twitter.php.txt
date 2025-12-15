<?php
/*
Plugin Name: Twitter Plugin
Plugin URI:  http://bestwebsoft.com/plugin/
Description: Plugin to add a link to the page author to twitter.
Author: BestWebSoft
Version: 2.15
Author URI: http://bestwebsoft.com/
License: GPLv2 or later
*/

/*
	 Copyright 2011  BestWebSoft  ( admin@bestwebsoft.com )
	
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

//add settings links

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
				<h3><?php _e( 'Activated plugins', 'twitter' ); ?></h3>
				<?php foreach( $array_activate as $activate_plugin ) { ?>
				<div style="float:left; width:200px;"><?php echo $activate_plugin['title']; ?></div> <p><a href="<?php echo $activate_plugin['link']; ?>" target="_blank"><?php echo __( "Read more", 'twitter'); ?></a> <a href="<?php echo $activate_plugin['url']; ?>"><?php echo __( "Settings", 'twitter'); ?></a></p>
				<?php } ?>
			</div>
			<?php } ?>
			<?php if( 0 < $count_install ) { ?>
			<div>
				<h3><?php _e( 'Installed plugins', 'twitter' ); ?></h3>
				<?php foreach($array_install as $install_plugin) { ?>
				<div style="float:left; width:200px;"><?php echo $install_plugin['title']; ?></div> <p><a href="<?php echo $install_plugin['link']; ?>" target="_blank"><?php echo __( "Read more", 'twitter'); ?></a></p>
				<?php } ?>
			</div>
			<?php } ?>
			<?php if( 0 < $count_recomend ) { ?>
			<div>
				<h3><?php _e( 'Recommended plugins', 'twitter' ); ?></h3>
				<?php foreach( $array_recomend as $recomend_plugin ) { ?>
				<div style="float:left; width:200px;"><?php echo $recomend_plugin['title']; ?></div> <p><a href="<?php echo $recomend_plugin['link']; ?>" target="_blank"><?php echo __( "Read more", 'twitter'); ?></a> <a href="<?php echo $recomend_plugin['href']; ?>" target="_blank"><?php echo __( "Download", 'twitter'); ?></a> <a class="install-now" href="<?php echo get_bloginfo( "url" ) . $recomend_plugin['slug']; ?>" title="<?php esc_attr( sprintf( __( 'Install %s' ), $recomend_plugin['title'] ) ) ?>" target="_blank"><?php echo __( 'Install now from wordpress.org', 'twitter' ) ?></a></p>
				<?php } ?>
				<span style="color: rgb(136, 136, 136); font-size: 10px;"><?php _e( 'If you have any questions, please contact us via plugin@bestwebsoft.com or fill in our contact form on our site', 'twitter' ); ?> <a href="http://bestwebsoft.com/contact/">http://bestwebsoft.com/contact/</a></span>
			</div>
			<?php } ?>
		</div>
		<?php
	}
}

// Register settings for plugin
if( ! function_exists( 'twttr_settings' ) ) {
	function twttr_settings() {
		global $twttr_options_array;

		$twttr_options_array_defaults = array(
			'twttr_url_twitter' => 'admin',
			'twttr_position' => ''
		);

		if( ! get_option( 'twttr_options_array' ) )
			add_option( 'twttr_options_array', $twttr_options_array_defaults, '', 'yes' );

		$twttr_options_array = get_option( 'twttr_options_array' );

		$twttr_options_array = array_merge( $twttr_options_array_defaults, $twttr_options_array );
	}
}

//add meny
if(!function_exists ( 'twttr_add_pages' ) ) {
	function twttr_add_pages() {
		add_menu_page( 'BWS Plugins', 'BWS Plugins', 'manage_options', 'bws_plugins', 'bws_add_menu_render', plugins_url( 'images/px.png', __FILE__ ), 1001); 
		add_submenu_page('bws_plugins', __( 'Twitter Options', 'twitter' ), __( 'Twitter', 'twitter' ), 'manage_options', 'twitter.php', 'twttr_settings_page');

		//call register settings function
		add_action( 'admin_init', 'twttr_settings' );
	}
}
//add meny.End
		
//add.Form meny.
if (!function_exists ( 'twttr_settings_page' ) ) {
	function twttr_settings_page () {
		global $twttr_options_array;
		$message = "";
		$error = "";
		if ( isset ( $_REQUEST['twttr_position'] ) && isset ( $_REQUEST['twttr_url_twitter'] ) && check_admin_referer( plugin_basename(__FILE__), 'twttr_nonce_name' ) ) {
			$twttr_options_array['twttr_url_twitter'] = $_REQUEST['twttr_url_twitter'];
			$twttr_options_array['twttr_position'] = $_REQUEST['twttr_position'];
			update_option ( "twttr_options_array", $twttr_options_array );
			$message = __( "Options saved.", 'twitter' );
		} ?>
		<div class="wrap">
			<div class="icon32 icon32-bws" id="icon-options-general"></div>
			<h2><?php echo __( "Twitter Options", 'twitter' ); ?></h2>
			<div class="updated fade" <?php if( empty( $message ) || $error != "" ) echo "style=\"display:none\""; ?>><p><strong><?php echo $message; ?></strong></p></div>
			<div class="error" <?php if( "" == $error ) echo "style=\"display:none\""; ?>><p><strong><?php echo $error; ?></strong></p></div>
			<div>
				<form method='post' action="admin.php?page=twitter.php">
					<table class="form-table">
						<tr valign="top">
							<th scope="row" colspan="2"><?php echo __( 'Settings for the button "Follow Me":', 'twitter' ); ?></th>
						</tr>					
						<tr valign="top">
							<th scope="row">
								<?php echo __( "Enter your username:", 'twitter' ); ?>
							</th>
							<td>
								<input name='twttr_url_twitter' type='text' value='<?php echo $twttr_options_array['twttr_url_twitter'] ?>'/><br />
								<span style="color: rgb(136, 136, 136); font-size: 10px;"><?php echo __( 'If you do not have Twitter account yet you need to create it using this link', 'twitter' ); ?> <a target="_blank" href="https://twitter.com/signup">https://twitter.com/signup</a> .</span><br />
								<span style="color: rgb(136, 136, 136); font-size: 10px;"><?php echo __( 'Put a shortcode [follow_me] on necessary page or post to use "Follow Me" button.', 'twitter' ); ?></span><br />
								<span style="color: rgb(136, 136, 136); font-size: 10px;"><?php echo __( 'If you would like to utilize this button in another place, please put strings below into the template source code', 'twitter' ); ?>	&#60;?php if ( function_exists( 'follow_me' ) ) echo follow_me(); ?&#62;</span>
							</td>
						</tr>
						<tr valign="top">
							<th scope="row" colspan="2"><?php echo __( 'Settings for the button "Twitter":', 'twitter' ); ?></th>
						</tr>					
						<tr>
							<th>
								<?php echo __( 'Choose a position for an icon "Twitter":', 'twitter' ); ?>
							</th>
							<td>
								<input style="margin-top:3px;" type="radio" name="twttr_position" value="1" <?php if ( $twttr_options_array['twttr_position'] == 1 ) echo 'checked="checked"'?> /> <label for="twttr_position"><?php echo __( 'Top position', 'twitter' ); ?></label><br />
								<input style="margin-top:3px;" type="radio" name="twttr_position" value="0" <?php if ( $twttr_options_array['twttr_position'] == 0 ) echo 'checked="checked"'?> /> <label for="twttr_position"><?php echo __( 'Bottom position', 'twitter' ); ?></label><br />
								<span style="color: rgb(136, 136, 136); font-size: 10px;"><?php echo __( 'When clicking this sign a user adds to their twitter page article that they liked along with a link to it.', 'twitter' ); ?></span><br />
							</td>
						</tr>
						<tr>
						<td colspan="2">
							<input type="submit" class="button-primary" value="<?php _e( 'Save Changes' ) ?>" />
						</td>
					</tr>
					</table>
					<?php wp_nonce_field( plugin_basename(__FILE__), 'twttr_nonce_name' ); ?>
				</form>
			</div>
		</div>
	<?php
	}		
}
//add.Form meny.End.	
	
// score code[follow_me]
if (!function_exists('twttr_follow_me')){
	function twttr_follow_me() {
		global $twttr_options_array;
		return '<div class="twttr_follow"><a href="http://twitter.com/'.$twttr_options_array["twttr_url_twitter"].'" target="_blank" title="Follow me">
				 <img src="'.plugins_url('images/twitter-follow.gif', __FILE__).'" alt="Follow me" />
			  </a></div>';
	}
}

	
//Positioning in the page	
if(!function_exists( 'twttr_twit' ) ) {
	function twttr_twit( $content ) {
		global $post;
		global $twttr_options_array;
		$permalink_post = get_permalink($post->ID);
		$title_post = $post->post_title;
		if( $title_post  == 'your-post-page-title' )
			return $content;

		$position = $twttr_options_array[ 'twttr_position'];
		$str = '<div class="twttr_button">
				<a href="http://twitter.com/share?url='.$permalink_post.'&text='.$title_post.'" target="_blank" title="'.__( 'Click here if you liked this article.', 'twitter' ).'">
					<img src="'.plugins_url('images/twitt.gif', __FILE__).'" alt="Twitt" />
				</a>
			</div>';
		if ( $position ){
			return $str.$content;
		}
		else{
			return $content.$str;
		}
	}
}
//Positioning in the page.End.


function twttr_action_links( $links, $file ) {
		//Static so we don't call plugin_basename on every plugin row.
	static $this_plugin;
	if ( ! $this_plugin ) $this_plugin = plugin_basename(__FILE__);

	if ( $file == $this_plugin ){
			 $settings_link = '<a href="admin.php?page=twitter.php">' . __( 'Settings', 'twitter' ) . '</a>';
			 array_unshift( $links, $settings_link );
		}
	return $links;
} // end function twttr_bttn_plgn_action_links

function twttr_links($links, $file) {
	$base = plugin_basename(__FILE__);
	if ($file == $base) {
		$links[] = '<a href="admin.php?page=twitter.php">' . __( 'Settings','twitter' ) . '</a>';
		$links[] = '<a href="http://wordpress.org/extend/plugins/twitter-plugin/faq/" target="_blank">' . __( 'FAQ','twitter' ) . '</a>';
		$links[] = '<a href="Mailto:plugin@bestwebsoft.com">' . __( 'Support','twitter' ) . '</a>';
	}
	return $links;
}

//Function '_plugin_init' are using to add language files.
if ( ! function_exists ( 'twttr_plugin_init' ) ) {
	function twttr_plugin_init() {
		load_plugin_textdomain( 'twitter', false, dirname( plugin_basename( __FILE__ ) ) . '/languages/' ); 
	}
} // end function twttr_plugin_init


if ( ! function_exists ( 'twttr_admin_head' ) ) {
	function twttr_admin_head() {
		wp_register_style( 'twttrStylesheet', plugins_url( 'css/style.css', __FILE__ ) );
		wp_enqueue_style( 'twttrStylesheet' );
	}
}

add_action( 'init', 'twttr_plugin_init' );
add_action( 'init', 'twttr_settings' );

add_action( 'admin_enqueue_scripts', 'twttr_admin_head' );
add_action( 'wp_enqueue_scripts', 'twttr_admin_head' );

// adds "Settings" link to the plugin action page
add_filter( 'plugin_action_links', 'twttr_action_links',10,2);

//Additional links on the plugin page
add_filter( 'plugin_row_meta', 'twttr_links',10,2);

add_filter( "the_content", "twttr_twit" );

add_action ( 'admin_menu', 'twttr_add_pages' );

add_shortcode( 'follow_me', 'twttr_follow_me' );

?>
