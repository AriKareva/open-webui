<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';

	export let className = 'size-8';
	export let src = `${WEBUI_BASE_URL}/static/favicon.png`;

	const getThemeLogo = () =>
		typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
			? '/hecate-black.svg'
			: '/hecate-white.svg';
</script>

<img
	aria-hidden="true"
	src={src === '' || src === `${WEBUI_BASE_URL}/static/favicon.png`
		? getThemeLogo()
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
		e.currentTarget.src = getThemeLogo();
	}}
/>
