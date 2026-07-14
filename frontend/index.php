<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Szczytnik - Panel Główny</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f4f4f4; color: #333; }
        .container { max-width: 1000px; background: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin: 0 auto; }
        h1 { color: #0056b3; margin-top: 0; }
        .status { padding: 10px; background: #e2f0d9; border: 1px solid #b4c6e7; margin-bottom: 20px; border-radius: 4px; }
        .menu-list { list-style: none; padding: 0; display: flex; gap: 15px; border-bottom: 2px solid #0056b3; padding-bottom: 15px; margin-bottom: 20px; flex-wrap: wrap; }
        .menu-list li { margin: 0; }
        .menu-list li a { text-decoration: none; color: #0056b3; font-weight: bold; padding: 8px 12px; background: #e6f0fa; border-radius: 4px; transition: background 0.2s; display: inline-block; }
        .menu-list li a:hover { background: #d0e2f5; }
        .menu-list li a.active { background: #0056b3; color: white; }
        
        /* Stylistyka tabeli bazy danych */
        .db-table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 4px; overflow: hidden; }
        .db-table th, .db-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e0e0e0; vertical-align: top; }
        .db-table th { background-color: #0056b3; color: white; font-weight: bold; }
        .db-table tr:nth-child(even) { background-color: #f9f9f9; }
        .db-table tr:hover { background-color: #f1f5f9; }
        
        .badge { display: inline-block; padding: 3px 8px; background: #e2e8f0; color: #4a5568; border-radius: 12px; font-size: 0.8em; margin: 2px 2px 2px 0; font-weight: 500; }
        .abstract-text { font-size: 0.9em; line-height: 1.5; color: #4a5568; text-align: justify; }
        .error-msg { padding: 15px; background: #fed7d7; border: 1px solid #feb2b2; color: #9b2c2c; border-radius: 4px; margin-top: 20px; }
        .info-msg { padding: 15px; background: #ebf8ff; border: 1px solid #bee3f8; color: #2b6cb0; border-radius: 4px; margin-top: 20px; }
        .back-link { display: inline-block; margin-top: 20px; color: #0056b3; text-decoration: none; font-weight: bold; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>

<div class="container">
    <h1>System Szczytnik</h1>
    
    <div class="status">
        <strong>Status połączenia z API:</strong> 
        <?php
            $api_url = 'http://backend:8000/';
            $response = @file_get_contents($api_url);
            if ($response) {
                $data = json_decode($response, true);
                echo "Połączono! Odpowiedź API: " . htmlspecialchars($data['message']);
            } else {
                echo "<span style='color:red;'>Brak połączenia z API backendu (port 8000).</span>";
            }
        ?>
    </div>

    <h3>Panel główny</h3>
    <?php
        // Pobieramy aktualną akcję z adresu URL (np. ?action=db_view), domyślnie pusta
        $action = isset($_GET['action']) ? $_GET['action'] : '';
    ?>
    
    <ul class="menu-list">
        <li><a href="?action=catalog" class="<?php echo $action === 'catalog' ? 'active' : ''; ?>">Przeglądaj katalog artykułów</a></li>
        <li><a href="?action=search" class="<?php echo $action === 'search' ? 'active' : ''; ?>">Wyszukiwarka AI</a></li>
        <li><a href="?action=upload" class="<?php echo $action === 'upload' ? 'active' : ''; ?>">Wgraj nowe czasopismo (PDF)</a></li>
        <li><a href="?action=db_view" class="<?php echo $action === 'db_view' ? 'active' : ''; ?>" style="background-color: #4a5568; color: white;">Wyświetl całą bazę danych</a></li>
    </ul>

    <?php if ($action === 'db_view'): ?>
        <h2>Podgląd Bazy Danych</h2>
        <p style="color: #666; font-style: italic;">Prezentacja pierwszych 3 pociętych artykułów z każdego wgranego numeru czasopisma:</p>

        <?php
            // Odpytujemy nasz nowy endpoint w FastAPI
            $db_api_url = 'http://backend:8000/api/debug/database-view';
            $db_response = @file_get_contents($db_api_url);

            if ($db_response !== false) {
                $articles = json_decode($db_response, true);
                
                if (isset($articles['error'])) {
                    echo "<div class='error-msg'><strong>Błąd backendu:</strong> " . htmlspecialchars($articles['error']) . "</div>";
                } elseif (empty($articles)) {
                    echo "<div class='info-msg'>Baza danych jest obecnie pusta. Wgraj czasopismo i poczekaj, aż Worker je przetworzy!</div>";
                } else {
                    echo '<table class="db-table">';
                    echo '<thead>';
                    echo '<tr>';
                    echo '<th style="width: 15%;">Czasopismo</th>';
                    echo '<th style="width: 23%;">Tytuł artykułu</th>';
                    echo '<th style="width: 15%;">Autor</th>';
                    echo '<th style="width: 7%; text-align: center;">Strona</th>';
                    echo '<th style="width: 18%;">Słowa kluczowe</th>';
                    echo '<th style="width: 22%;">Streszczenie</th>';
                    echo '</tr>';
                    echo '</thead>';
                    echo '<tbody>';

                    foreach ($articles as $art) {
                        echo '<tr>';
                        echo '<td>';
                        echo '<strong>' . htmlspecialchars($art['issue_title']) . '</strong><br>';
                        echo '<small style="color: #718096;">Nr: ' . htmlspecialchars($art['issue_number']) . '</small>';
                        echo '</td>';
                        echo '<td style="font-weight: 600; color: #2d3748;">' . htmlspecialchars($art['article_title']) . '</td>';
                        echo '<td style="color: #4a5568;">' . htmlspecialchars($art['author']) . '</td>';
                        echo '<td style="text-align: center; font-weight: bold; color: #2b6cb0;">' . htmlspecialchars($art['start_page']) . '</td>';
                        
                        // Słowa kluczowe w formie odznak (badges)
                        echo '<td>';
                        if (!empty($art['keywords'])) {
                            $keywords_array = explode(',', $art['keywords']);
                            foreach ($keywords_array as $kw) {
                                echo '<span class="badge">' . htmlspecialchars(trim($kw)) . '</span>';
                            }
                        } else {
                            echo '<span style="color: #cbd5e0; font-style: italic;">Brak</span>';
                        }
                        echo '</td>';
                        
                        // Streszczenie z zachowaniem podziału na linie
                        echo '<td class="abstract-text">' . nl2br(htmlspecialchars($art['abstract'])) . '</td>';
                        echo '</tr>';
                    }

                    echo '</tbody>';
                    echo '</table>';
                }
            } else {
                echo "<div class='error-msg'><strong>Błąd połączenia:</strong> Nie udało się skomunikować z API backendu pod adresem: <code>$db_api_url</code>.<br>Upewnij się, że zrestartowałeś kontener backendu (<code>podman restart szczytnik_backend</code>).</div>";
            }
        ?>
        <a href="index.php" class="back-link">← Powrót do strony głównej</a>

    <?php elseif ($action === 'catalog'): ?>
        <h2>Katalog artykułów</h2>
        <div class="info-msg">Moduł przeglądania katalogu w przygotowaniu.</div>
        <a href="index.php" class="back-link">← Powrót</a>

    <?php elseif ($action === 'search'): ?>
        <h2>Wyszukiwarka AI</h2>
        <div class="info-msg">Interfejs wyszukiwania semantycznego opartego o wektory i Gemini AI w przygotowaniu.</div>
        <a href="index.php" class="back-link">← Powrót</a>

    <?php elseif ($action === 'upload'): ?>
        <h2>Wgraj nowe czasopismo (PDF)</h2>
        <div class="info-msg">Interfejs przesyłania czasopism w przygotowaniu.</div>
        <a href="index.php" class="back-link">← Powrót</a>

    <?php else: ?>
        <div style="margin-top: 20px; padding: 15px; background: #eef2f7; border-left: 4px solid #0056b3; border-radius: 4px; line-height: 1.5;">
            Witamy w systemie archiwizacji i analizy czasopism krajoznawczych <strong>Szczytnik</strong>. <br>
            Wybierz jedną z opcji z menu powyżej, aby rozpocząć przeglądanie lub analizowanie dokumentów.
        </div>
    <?php endif; ?>
</div>

</body>
</html>