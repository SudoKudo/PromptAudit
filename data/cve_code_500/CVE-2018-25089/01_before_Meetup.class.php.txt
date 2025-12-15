<?php
/**
 * Simple custom tag extension to render information from the Meetup API.
 *
 * PHP version 5
 *
 * @ingroup Extensions
 * @author  Geoff Baskwill <me@geoffbaskwill.ca>
 * @version 0.1
 * @link    https://github.com/glb/mediawiki-tag-extension-meetup
 * @license https://opensource.org/licenses/MIT MIT
 */

/**
 * Protect against register_globals vulnerabilities.
 * This line must be present before any global variable is referenced.
 */
if( !defined( 'MEDIAWIKI' ) ) {
	echo( "This is an extension to the MediaWiki package and cannot be run standalone.\n" );
	die( -1 );
}

// Extension credits that will show up on Special:Version
$wgExtensionCredits['parserhook'][] = array(
	'path' => __FILE__,
	'name' => 'Meetup',
	'version' => '0.1',
	'author' => 'Geoff Baskwill',
	'url' => 'https://github.com/glb/mediawiki-tag-extension-meetup',
	'descriptionmsg' => 'meetup-desc', // Message key in i18n file.
	'description' => 'Adds <code>&lt;meetup&gt;</code> tag for including Meetup information in pages',
);

/**
 * Simple custom tag extension to render information from the Meetup API.
 *
 * This class is based on the sample tag extension documented at
 * https://www.mediawiki.org/wiki/Manual:Tag_extensions
 *
 * Special thanks to the Magic:NoCache hook for the special magic
 * required to disable caching so that the page always uses fresh
 * data from the API.
 *
 * https://phabricator.wikimedia.org/diffusion/EMNC/browse/master/MagicNoCache.hooks.php
 *
 * @ingroup Extensions
 * @author  Geoff Baskwill <me@geoffbaskwill.ca>
 * @link    https://github.com/glb/mediawiki-tag-extension-meetup
 * @license https://opensource.org/licenses/MIT MIT
 */
class Meetup
{
	/**
	 * Register our custom render callback with the parser.
	 *
	 * @param Parser $parser The Parser object that the function should
	 *                       register its hook with.
	 *
	 * @return true
	 */
	public static function init( $parser )
	{
		// When the parser sees the <meetup> tag, it executes renderTag
		$parser->setHook( 'meetup', array( 'Meetup', 'renderTag') );
		return true;
	}

	/**
	 * Render <meetup> tag.
	 *
	 * This function renders a custom <meetup group="{group ID}" /> tag,
	 * reaching out to the meetup.com API to get details of upcoming and past
	 * meetups.
	 *
	 * @param string  $input  The content of the tag (ignored as we don't render it).
	 * @param array   $param  The array of parameters passed to the tag.
	 * @param Parser  $parser The Parser -- needed to turn off caching
	 * @param PPFrame $frame  ignored
	 *
	 * @global OutputPage $wgOut The OutputPage -- we need it to turn off
	 *                           caching for this page.
	 * @global array      $wgAction The action being performed -- we need it to
	 *                              control whether we turn off caching.
	 *
	 * @return string content to be displayed
	 */
	public static function renderTag( $input, $param = array(), $parser = null, $frame = false) {
		global $wgOut, $wgAction;

		$wgOut->addModules( 'ext.meetup.base' );

		if ( !in_array($wgAction, ['submit', 'edit']) ) {
			$parser->disableCache();
			$wgOut->enableClientCache(false);
		}

		// This isn't particularly great if the wiki is set up with a CSP that
		// disallows inline CSS. A better solution would move the CSS to a
		// resource.

//		$ret = '<style>' .
//		       '.meetup-description { font-weight: lighter; display: block; }' .
//		       '.meetup-venue { font-style: italic; display: block; }' .
//		       'li.event { margin-bottom: 1em; }' .
//		       '</style>';

		$ret .= Html::rawElement( 'h2', array(), wfMessage('meetup-header')->parse() );

		$group = $param['group'];

		if ( $group === false || $group == "" ||  $group == "{groupID}" ) {
			$ret .= Html::rawElement( 'p', array(),
				wfMessage( 'meetup-missing-group-info' )->parse()
			);
			return $ret;
		}

		// Ensure that the user-provided input (group ID) is encoded for the
		// context it will be used in -- which is always a URL
		$group = urlencode($group);

		$ret .= Html::rawElement( 'a', array(
				'target' => '_blank',
				'rel' => 'nofollow',
				'class' => 'external text meetup-badge',
				'href' => wfMessage( 'meetup-group-ui-url', $group )->plain(),
			), wfMessage( 'meetup-group-link-text')->parse() );

		$ret .= Meetup::_getAndRenderEvents(
			$group, 'upcoming', 5, 'false',
			'meetup-upcoming-events-header',
			'meetup-all-upcoming-events',
			'meetup-no-events-scheduled'
		);

		$ret .= Meetup::_getAndRenderEvents(
			$group, 'past', 5, 'true',
			'meetup-past-events-header',
			'meetup-all-past-events',
			'meetup-no-past-events'
		);

		return $ret;
	}

	/**
	 * Retrieve events from the meetup.com API and render them.
	 *
	 * This function retrieves the desired number of events from the API
	 * and renders the event details in a list.
	 *
	 * @param string $group          The meetup.com group ID.
	 * @param string $status         The type of events (past, upcoming, ...)
	 *                               to retrieve and render.
	 * @param int	 $count          The number of events to render.
	 * @param string $desc           'true' to order events in descending order,
	 *                               'false' otherwise.
	 * @param string $header_message The message (see i18n/*.json) to render as
	 *                               the header for this section.
	 * @param string $link_message   The message (see i18n/*.json) to render as
	 *                               the "see all" link for this section.
	 * @param string $empty_message  The message (see i18n/*.json) to render if
	 *                               there are no events for this section.
	 *
	 * @return string content to be displayed
	 */
	private static function _getAndRenderEvents( $group, $status, $count,
		$desc, $header_message, $link_message, $empty_message
	) {
		$url = sprintf( '%s/%s/events' .
				'?sign=true&photo-host=public&page=%d&status=%s&desc=%s',
			wfMessage( 'meetup-api-base-url' )->plain(),
			$group,
			$count,
			$status,
			$desc
		);

		wfDebugLog( 'meetup', 'Retrieving events from API URL ' . $url );

		$response = @file_get_contents( $url );
		if ( $response === false ) {
			wfDebugLog( 'meetup', 'Unable to retrieve events.' );
			return "";
		}

		$events = json_decode( $response, true );

		$ret .= Html::rawElement( 'h3', array(), wfMessage( $header_message )->parse() );

		if (count($events) > 0 ) {
			$ret .= '<ul>';
			foreach ( $events as $event ) {
				// First get rid of all the tags and then escape any remaining
				// special characters in the description.
				$description = htmlspecialchars(
					preg_replace(
						'/<.*?>/', '',
						$event['description']
					),
					ENT_COMPAT | ENT_HTML401,
					ini_get( "default_charset" ), false
				);

				// Then get rid of newlines; they make the formatting in the
				// wiki go bad.
				$description = preg_replace( '/\n+/', ' ', $description );

				// Then cut to a max of 400 characters; if there are more then
				// add a link to the event.
				$description = preg_replace(
					'/(.{400})(.+)/',
					'\1 ' . Html::rawElement( 'a', array(
						'target' => '_blank',
						'rel' => 'nofollow',
						'class' => 'external text',
						'href' => $event['link'],
					), wfMessage( 'meetup-read-more' )->parse() ),
					$description
				);

				$ret .= Html::rawElement( 'li', array(
						'class' => 'event',
					), Html::rawElement( 'a', array(
						'target' => '_blank',
						'rel' => 'nofollow',
						'class' => 'external text',
						'href' => $event['link']
					), sprintf( '%s (%s): %s',
						date( 'M j, Y', $event['time']/1000 ),
						htmlspecialchars( $event['local_time'] ),
						htmlspecialchars( $event['name'] ) )
					) . Html::rawElement( 'span', array(
						'class' => 'meetup-venue',
					), sprintf( '%s, %s · %s, %s',
						htmlspecialchars( $event['venue']['name'] ),
						htmlspecialchars( $event['venue']['address_1'] ),
						htmlspecialchars( $event['venue']['city'] ),
						htmlspecialchars( $event['venue']['state'] ) )
					) . Html::rawElement( 'span', array(
						'class' => 'meetup-description',
					), $description ) // user-provided input has already been
				);                       // escaped using htmlspecialchars
			}
			$ret .= '</ul>';

			$ret .= Html::rawElement( 'a', array(
					'target' => '_blank',
					'rel' => 'nofollow',
					'class' => 'external text',
					'href' => wfMessage(
						'meetup-events-ui-url', $group, $status
					)->plain(),
				), wfMessage( $link_message )->parse() );
		} else {
			$ret .= wfMessage( $empty_message )->parse();
		}

		return $ret;
	}

}

?>
