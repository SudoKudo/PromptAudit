
<div style="display:none;">
<?php submit_button( __( 'Save' ), 'button', 'save' ); ?>
<input type="hidden" name="post_status" value="publish" />
</div>

<div id="major-publishing-actions">
<?php do_action('post_submitbox_start'); ?>
<div id="delete-action">
<?php
if ( current_user_can( "delete_post", $post->ID ) ) {
	if ( !EMPTY_TRASH_DAYS )
		$delete_text = __('Delete Permanently');
	else
		$delete_text = __('Move to Trash');
	?>
	<a class="submitdelete deletion" href="<?php echo esc_url(get_delete_post_link($post->ID)); ?>"><?php echo $delete_text; ?></a><?php
} ?>
</div>

<div id="publishing-action">
<span class="spinner"></span>
	<input name="original_publish" type="hidden" id="original_publish" value="Save" />
	<?php submit_button('Save', 'primary button-large', 'publish', false, array() ); ?>
</div>
<div class="clear"></div>

</div>

