<?php
/*
Plugin Name: Beeliked Microsite
Plugin URI: http://beeliked.com
Description: Allows the insertion of code to display a BeeLiked microsite within an iframe. The tag to insert the code is: <code>[BEELIKED_MICROSITE]</code>, containing url, width, height and autosize parameters.
Version: 1.0.2
Author: Beeliked
Author URI: http://beeliked.com
License: GPLv2 or later
Text Domain: beeliked
*/

/*
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


/*
1.0   - Initial release
1.0.1 - Documentation change
*/

include (dirname (__FILE__).'/plugin.php');

class BeelikedMicrosite extends BeelikedMicrosite_Plugin
{
	function BeelikedMicrosite ()
	{
		$this->register_plugin ('beelikedmicrosite', __FILE__);
		
		$this->add_action('template_redirect', 'load_js');
		
		add_shortcode('BEELIKED_MICROSITE', array($this, 'embed_handler'));
		
		$this->add_filter('tiny_mce_version', array($this, 'refresh_mce'));
		$this->add_action('init', 'add_beeliked_button');
		
		$this->add_action('admin_print_footer_scripts', 'add_quicktags');
	}
	
	/* TINYMCE */
	
	function refresh_mce () 
	{
		$ver += 3;
		return $ver;
	}
	
	function add_beeliked_button() 
	{
      if ( ! current_user_can('edit_posts') && ! current_user_can('edit_pages') )
        return;
 
      // Add only in Rich Editor mode
      //if ( get_user_option('rich_editing') == 'true') {
        $this->add_filter("mce_external_plugins", "add_tinymce_plugin");        
		$this->add_filter('mce_buttons', 'register_tinymce_button');
		
      //}
	}
	
	function add_tinymce_plugin($plugin_array)
	{
	  $plugin_array['beelikedmicrosite'] = plugins_url('/js/editor_plugin.js', __file__);
	  return $plugin_array;
	}
	
	function register_tinymce_button($buttons)
	{
	  array_push($buttons, "beelikedmicrosite");
      return $buttons;
	}
	
	function add_quicktags()
	{
		if (wp_script_is('quicktags'))
		{
		?>
		<script type="text/javascript">
		QTags.addButton('beeliked_microsite', 'Beeliked Microsite', '[BEELIKED_MICROSITE url="', '" width="100%" height="1400px" autosize="1"]', '' );
		</script>
		<?php 
		}
	}
	
	/* SHORTCODE */
	
	function load_js() 
	{
		wp_register_script('jquery_iframeResizer', plugins_url('/js/iframeResizer.min.js', __file__), array('jquery'));		
		wp_enqueue_script('jquery_iframeResizer');
	}
	
	protected $iframeId = 0;
	
	function embed_handler($atts = array()) 
	{
		shortcode_atts(array(
			'url' => 'http://beta.beeliked.com',
			'width' => '100%',
			'height' => '1400px',
			'autosize' => true
		), $atts);
		
		$autosize = $atts['autosize'] ? 1 : 0;
		
		$this->iframeId++;
		$return = "<iframe load-url=\"{$atts['url']}\" id=\"bee-microsite-iframe-{$this->iframeId}\" class=\"bee-microsite-iframe\" width=\"{$atts['width']}\" height=\"{$atts['height']}\" data-autosize=\"{$autosize}\" frameborder=\"0\"></iframe>
<script type=\"text/javascript\" src=\"http://beta.beeliked.com/microsite/js/beeliked.clientIframe.js\"></script>
<script type=\"text/javascript\">jQuery(document).ready(function() { jQuery('.bee-microsite-iframe[data-autosize=1]').iFrameResize({heightCalculationMethod : 'max', checkOrigin: false}); });</script>";
		return $return;
	}
}

$beelikedMicrosite = new BeelikedMicrosite;
?>
