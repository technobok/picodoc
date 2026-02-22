    function docReady(fn) {
        // see if DOM is already available
        if (document.readyState === "complete" || document.readyState === "interactive") {
            // call on next available tick
            setTimeout(fn, 1);
        } else {
            document.addEventListener("DOMContentLoaded", fn);
        }
    };

    // Switch between static asciidoc toc and dynamic tocify toc based on browser size
    // This is set to match the media selectors in the asciidoc CSS
    // Without this, we keep the dynamic toc even if it is moved from the side to preamble
    // position which will cause odd scrolling behavior
    function handleTocOnResize() {
        if (document.body.clientWidth < 768) {
            // hide the generated js toc
            e = document.getElementById("generated-toc");
            e.classList.add('hide');
            e.classList.remove('show');

            // show the default asciidoc inline toc
            var l = document.getElementsByClassName("sectlevel0");
            for (let i of l) {
                i.classList.add('show');
                i.classList.remove('hide');

            }
            var l = document.getElementsByClassName("sectlevel1");
            for (let i of l) {
                i.classList.add('show');
                i.classList.remove('hide');

            }
        }
        else {
            // show the generated js toc
            e = document.getElementById("generated-toc");
            e.classList.add('show');
            e.classList.remove('hide');

            // hide the default asciidoc inline toc
            var l = document.getElementsByClassName("sectlevel0");
            for (let i of l) {
                i.classList.add('hide');
                i.classList.remove('show');

            }
            var l = document.getElementsByClassName("sectlevel1");
            for (let i of l) {
                i.classList.add('hide');
                i.classList.remove('show');

            }

        }
    };

    docReady(function() {
        // Add a new container for the tocify toc into the existing toc so we can re-use its
        // styling
        console.debug("ready");
/*
        var t = document.getElementById("toc");
        t.insertAdjacentHTML("beforeend", "<div id='generated-toc'></div>");
        tocbot.init({
            tocSelector: '#generated-toc',
            contentSelector: '#content',
            //headingSelector: 'h1, h2, h3, h4, h5',
            headingSelector: document.getElementById("content").getElementsByTagName("h1").length > 0 ? "h1,h2,h3,h4,h5" : "h2,h3,h4,h5",
            hasInnerContainers: true,
            listClass: 'toc-list',
            listItemClass: 'toc-list-item',
            activeListItemClass: 'toc-list-item-focus',
            activeLinkClass: 'toc-is-active-link',
            // without tocScrollOffset, the highlighted toc item is above the
            // visible when scrolling up
            tocScrollOffset: 50
        });

        // $(window).resize(handleTocOnResize);
        addEventListener("resize", (event) => { handleTocOnResize() });
        handleTocOnResize();


        const toggleCheckbox = document.getElementById('mode-checkbox');
        const root = document.documentElement;

        toggleCheckbox.addEventListener('change', () => {
          // smooth transitions on change
          var toc = document.getElementById('toc');
          if (toc) { toc.classList.add('trans'); }
          document.body.classList.add('trans');

          if (toggleCheckbox.checked) {
            document.body.classList.add('dark-mode');
            //root.classList.add('dark-mode');
            localStorage.setItem('theme', 'dark');
          } else {
            document.body.classList.remove('dark-mode');
            //root.classList.remove('dark-mode');
            localStorage.setItem('theme', 'light');
          }
        });
*/
        window.addEventListener('load', () => {
          if (localStorage.getItem('theme') === 'dark') {
            toggleCheckbox.checked = true;
            document.body.classList.add('dark-mode');
            //root.classList.add('dark-mode');
          }
        });
    });

