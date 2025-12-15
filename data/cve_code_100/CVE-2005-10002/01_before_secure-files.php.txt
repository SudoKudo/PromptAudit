<?php
/*
Plugin Name: Secure Files
Plugin URI: http://www.almosteffortless.com/wordpress/
Description: This plugin allows you to upload and download files from outside of your web document root for security purposes. When used in conjunction with a plugin that requires a user to be logged in to see your site, you can restrict file downloads to users that are logged in. It can be found in Manage -> Secure Files.
Author: Trevor Turk
Version: 1.1
Author URI: http://www.almosteffortless.com/
*/ 

/*  Copyright 2005  Trevor Turk  (email : trevorturk@yahoo.com)

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/

	// setting options
	function sf_options() {
		if ( isset($_POST['sf_directory']) ) {
			$sf_directory = $_POST['sf_directory'];
			update_option('sf_directory', $sf_directory, '','');
		}
		if ( isset($_POST['sf_prefix']) ) {
			$sf_prefix = $_POST['sf_prefix'];
			update_option('sf_prefix', $sf_prefix, '','');
		}
	
	}
		
	// uploading files
	function sf_uploads() {
		if ( isset($_FILES['sf_upload']) ) {
			$sf_directory = get_option('sf_directory');
			$sf_prefix = get_option('sf_prefix');
			$uploadfile = $sf_directory . $_FILES['sf_upload']['name'];
			$file = $_FILES['sf_upload']['name'];
				if (@move_uploaded_file($_FILES['sf_upload']['tmp_name'], $uploadfile)) {
					@chmod($uploadfile, 0777);
					echo '<div class="updated">';
					echo '<p>The file <b>'. $_FILES['sf_upload']['name'] .'</b> was uploaded successfully.</p>';
					echo "<p><small>You can link to it like so: <code>&lt;a href=\"?$sf_prefix=$file\"&gt;$file&lt;/a&gt;</code></small></p>";
					echo "<p><small>If this is an image, you can do this: <code>&lt;img src=\"?$sf_prefix=$file\" alt=\"$file\" /&gt;</code></small></p>";
					echo '</div>';
				}
			else {
				echo '<div class="updated">';
				echo '<p>Sorry, there was an error uploading <b>'. $_FILES['sf_upload']['name'] .'</b>. Please check your <b>Options</b> and the file you want to upload before trying again.</p>';
				echo '</div>';
			}
		}
	}
	
	// downloading files
	function sf_downloads() {
		$sf_prefix = get_option('sf_prefix');
		if (isset($_GET["$sf_prefix"])) {
			$downloadfile = $_GET["$sf_prefix"];
			$sf_directory = get_option('sf_directory');
			$downloadfile = $sf_directory . $downloadfile;
			if (is_file($downloadfile)) {
				header('Content-Description: File Transfer'); 
				header('Content-Type: application/force-download'); 
				header('Content-Length: ' . filesize($downloadfile)); 
				header('Content-Disposition: attachment; filename="' . basename($downloadfile).'"'); 
				@readfile($downloadfile);
			}
			else {
				echo 'File not found';
			}
			exit;
		}
	}

	// add javascript toggle to the admin head
	function sf_admin_head_js() {
		echo '<script type="text/javascript">function toggle(idname) { if (document.getElementById(idname).style.display == "") { document.getElementById(idname).style.display = "none" } document.getElementById(idname).style.display = (document.getElementById(idname).style.display == "none") ? "block" : "none"; }</script>';
	}

	// for adding a entry to the wordpress options table for your secure file directory (outside of the web root)
	add_option('sf_directory', '/a/directory/outside/of/your/web/document/root/', 'Choose a directory outside of your web document root for file storage', $autoload);

	// for adding a entry to the wordpress options table for your secure file directory (outside of the web root)
	add_option('sf_prefix', 'file_id', 'Choose a prefix to use when downloading your secure files', $autoload);
		
	// for adding an admin menu under Manage -> Secure Files
	function sf_add_pages() {
		add_management_page('Secure Files', 'Secure Files', 8, __FILE__, 'sf_manage_page');
		}
			
	// Manage -> Secure Files admin subtab content
	function sf_manage_page() {
		
		sf_options();
		sf_uploads();
		
		$site_url = get_bloginfo('url');
		
		// get the secure files directory via get_option() if it has been updated via POST
		if ( isset($_POST['sf_directory']) ) {
			$sf_directory = $_POST['sf_directory'];
		}
		else {
			$sf_directory = get_option('sf_directory');
		}
		
		// get the secure files prefix via get_option() if it has been updated via POST
		if ( isset($_POST['sf_prefix']) ) {
			$sf_prefix = $_POST['sf_prefix'];
		}
		else {
			$sf_prefix = get_option('sf_prefix');
		}
	
		// show options update message
		if ( (isset($_POST['sf_directory'])) || (isset($_POST['sf_prefix'])) ) {
			echo '<div class="updated">';
			echo '<p>Secure Files Options have been updated.</p>';
			echo '</div>';
		}
				
		// check that secure files directory is writable (and exists)
		if (($sf_directory != '') && (!is_writable($sf_directory))) {
			echo '<div class="updated">';
			echo '<p><b>Warning</b>: The Secure Files Directory is not writable or does not exist. Please update your <b>Options</b> below.</p>';
			echo '</div>';
		}
		
		echo '<div class="wrap">';
		
		echo '<h2>Upload</h2>';
		
		echo '<form name="sf_upload" action="" method="post" enctype="multipart/form-data">';
		echo '<table width="100%" cellspacing="2" cellpadding="5" class="editform"><tr>';
		echo '<th width="20%" valign="top" scope="row">Upload a File: </th><td>';
		echo '<input type="file" name="sf_upload" id="sf_upload" size="35" class="uploadform" />';
		echo '<p><small>Choose a file to upload to your Secure Files Directory. Alternatively, you can upload files into your Secure Files Directory via <a href="http://codex.wordpress.org/FTP_Clients">FTP</a> and they will become available for download. <b>Warning</b>: If a file with the same name already exists, it will automatically be replaced.</small></p>';
		echo '</tr></table>';
		echo '<p class="submit"><input type="submit" name="Submit" value="Upload File &raquo;" /></p>';
		echo '</form>';
		
		echo '<h2>Download</h2>';
		
		echo '<table width="100%" cellspacing="2" cellpadding="5" class="editform"><tr>';
		echo '<th width="20%" valign="top" scope="row">Available Files: </th><td>';
		
		// get files in the secure directory
		if (is_dir($sf_directory)) {
			if ($handle = opendir($sf_directory)) {
				echo '<ul style="margin:0;padding:0;">';
				while (false !== ($file = readdir($handle))) {
					if ($file != "." && $file != "..") {
						echo "<li style='list-style-type:none;'><a href='$site_url/?$sf_prefix=$file'>$file</a>";
						echo "&nbsp;&nbsp;<a href=\"javascript:toggle('sf_toggle_$file')\" style='color:gray;'>&raquo</a>";
						echo "<ul id=\"sf_toggle_$file\" style='display:none;list-style-type:none;color:gray;padding-top:6px;'><li><small>Download Link: &lt;a href=\"?$sf_prefix=$file\"&gt;$file&lt;/a&gt;</small></li>";
						echo "<li><small>Display Image: &lt;img src=\"?$sf_prefix=$file\" alt=\"$file\" /&gt;</small></li></ul></li>";
					}
				}
			echo '</ul>';
			closedir($handle);
			}
		}
		
		echo '</td></tr></table>';	
		echo '<br /><h2>Options</h2>';
		
		echo '<form name="sf_options" action="" method="post">';
		echo '<table width="100%" cellspacing="2" cellpadding="5" class="editform">';
		echo '<tr><th width="20%" valign="top" scope="row">Secure Files Directory: </th><td>';
		echo '<input name="sf_directory" id="sf_directory" type="text" value="'.$sf_directory.'" size="50" /> ';
		echo '<p><small>Choose a directory <b>outside of your web document root</b> for storing your Secure Files. You will have to <a href="http://codex.wordpress.org/Uploading_WordPress_to_a_remote_host">create</a> this directory, and ensure that it is <a href="http://codex.wordpress.org/Make_a_Directory_Writable">writable</a>. If your site was located at <code>/home/users/myname/mydomain.com/</code> then you might want to use the directory <code>/home/users/myname/mydomain.com_files/</code> or something to that effect. To give you a starting point, your <b>insecure</b> Wordpress directory is located at <code>'.ABSPATH.'</code> and your Secure Directory should be <b>at least one level above this</b> and most likely more. Choose this directory carefully, because if it isn\'t outside of your web document root, your files will <b>NOT</b> be secure.</small></p>';
		echo '</td></tr>';
		echo '<tr><th width="20%" valign="top" scope="row">Secure Files Prefix: </th><td>';
		echo '<input name="sf_prefix" id="sf_prefix" type="text" value="'.$sf_prefix.'" size="20" /> ';
		echo '<p><small>Choose a prefix to use when downloading your Secure Files from your site. The default is <code>file_id</code> and you\'ll have to update any links you\'ve already put on your site if you change it. Click the <span style="color:gray;">&raquo</span> links to learn how to link to these files or include them as images in a Post or Page.</small></p>';
		echo '</td></tr>';
		echo '</table>';
		echo '<p class="submit"><input type="submit" name="Submit" value="Update Options &raquo;" /></p>';
		echo '</form>';
		
		echo '</div>';
		
	}

	// wordpress hooks
	add_action('admin_menu', 'sf_add_pages');
	add_action('admin_head', 'sf_admin_head_js');
	add_action('template_redirect', 'sf_downloads');

?>