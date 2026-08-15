# Render demo s PostgreSQL

Tato verze zachovava Flask banner, vzhled a rozvrhy. Free PostgreSQL slouzi pro kratkodobou ukazku.

Po nasazeni otevri `/admin/setup`, vytvor heslo spravce a v `/admin` nastav Skolu Online. Admin heslo a udaje Skoly Online se ukladaji sifrovane do PostgreSQL. Lokalni Linux bez DATABASE_URL dal pouziva lokalni sifrovane uloziste.

Instagram: lokalni kiosk zustava funkcni. Na Renderu nelze soucasnym Playwright oknem interaktivne predat 2FA kod z prohlizece navstevnika serverovemu profilu. Pro webovou verzi Instagramu je dalsim krokem oficialni Meta autorizace/token.
