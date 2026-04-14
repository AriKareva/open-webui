<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { onMount } from 'svelte';
	import { observeThemeLogo } from '$lib/utils/theme-logo';

	export let className = 'size-8';
	export let src = `${WEBUI_BASE_URL}/static/favicon.png`;
	let themeLogoSrc = '/hecate-white.svg';

	onMount(() => {
		return observeThemeLogo((logoSrc) => {
			themeLogoSrc = logoSrc;
		});
	});
</script>

<img
	aria-hidden="true"
	src={src === '' || src === `${WEBUI_BASE_URL}/static/favicon.png`
		? themeLogoSrc
		: src.startsWith(WEBUI_BASE_URL) ||
			  src.startsWith('https://www.gravatar.com/avatar/') ||
			  src.startsWith('data:') ||
			  src.startsWith('/')
			? src
			: `${WEBUI_BASE_URL}/user.png`}
	class=" {className} object-cover rounded-full"
	alt="profile"
	draggable="false"
	on:error={(e) => {
		e.currentTarget.src = themeLogoSrc;
	}}
/>
