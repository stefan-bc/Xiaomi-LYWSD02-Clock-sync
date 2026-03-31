export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    // Redirect pages.dev requests to the Access-protected custom domain
    if (url.hostname.endsWith(".pages.dev")) {
      return Response.redirect("https://clock.ectoplasma.org" + url.pathname, 302);
    }
    return env.ASSETS.fetch(request);
  }
};
