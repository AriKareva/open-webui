export const LIGHT_THEME_LOGO = '/hecate-white.svg';
export const DARK_THEME_LOGO = '/hecate-black.svg';

export const getThemeLogo = () => {
	if (typeof document === 'undefined') {
		return LIGHT_THEME_LOGO;
	}

	return document.documentElement.classList.contains('dark') ? DARK_THEME_LOGO : LIGHT_THEME_LOGO;
};

export const observeThemeLogo = (callback: (logoSrc: string) => void) => {
	if (typeof document === 'undefined') {
		callback(LIGHT_THEME_LOGO);
		return () => {};
	}

	const update = () => callback(getThemeLogo());
	update();

	const observer = new MutationObserver(update);
	observer.observe(document.documentElement, {
		attributes: true,
		attributeFilter: ['class']
	});

	return () => observer.disconnect();
};
