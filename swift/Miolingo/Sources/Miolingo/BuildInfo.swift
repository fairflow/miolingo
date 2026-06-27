// The build stamp, OVERWRITTEN by Scripts/make_app.sh with the git short-hash
// before each release build (then restored to "dev"), so the running app reports
// exactly the commit it was built from — compiled in, immune to plist caching.
enum BuildInfo { static let stamp = "dev" }
