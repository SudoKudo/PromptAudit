
<div class="error">
	<p>Gravity Forms DPS PxPay requires these missing PHP extensions. Please contact your website host to have these extensions installed.</p>
	<ul style="list-style-type: disc; padding-left: 2em;">
	<?php foreach ($missing as $ext): ?>
		<li><?php echo esc_html($ext); ?></li>
	<?php endforeach; ?>
	</ul>
</div>
