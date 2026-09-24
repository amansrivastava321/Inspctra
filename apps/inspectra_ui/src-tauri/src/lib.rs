use tauri::Manager;

#[tauri::command]
fn get_backend_url() -> String {
    // Always local — never proxied through a remote
    "http://127.0.0.1:8765".to_string()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // On startup: check if backend is reachable
            // No auto-launch of backend unless explicitly implemented and approved
            #[cfg(debug_assertions)]
            {
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .run(tauri::generate_context!())
        .expect("error while running Inspectra");
}
