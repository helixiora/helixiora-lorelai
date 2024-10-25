document.addEventListener('DOMContentLoaded', function() {
    if (typeof $ !== 'undefined') {
        $('#OrgTable').DataTable({
            "pagingType": "simple_numbers",
            "lengthMenu": [[10, 25, 50, -1], [10, 25, 50, "All"]],
            "order": [[0, "asc"]]
        });
    } else {
        console.error('jQuery is not loaded');
    }
});

function toggleCollapse() {
    var inviteSection = document.getElementById('inviteUserSection');
    inviteSection.classList.toggle('collapse');
}
