/**
 * 注册表单交互逻辑
 */

(function(window) {
    'use strict';

    // 注册表单数据
    var formData = {
        realName: '',
        idCard: '',
        email: '',
        verified: false,
        stationCode: '',
        stationName: '',
        usernameLetters: '',
        username: '',
        windowNo: '',
        password: ''
    };

    var currentStep = 1;
    var devCode = '';
    var searchTimeout = null;

    // 暴露formData给全局
    window.formData = formData;

    // 步骤导航
    window.goToStep = function(step) {
        // 更新步骤指示器
        document.querySelectorAll('.step-circle').forEach(function(circle) {
            var circleStep = parseInt(circle.dataset.step);
            circle.classList.remove('active', 'completed');
            if (circleStep < step) {
                circle.classList.add('completed');
            } else if (circleStep === step) {
                circle.classList.add('active');
            }
        });

        // 更新连接线
        document.querySelectorAll('.step-line').forEach(function(line, index) {
            if (index < step - 1) {
                line.classList.add('completed');
            } else {
                line.classList.remove('completed');
            }
        });

        // 更新进度条
        var progress = (step / 7) * 100;
        document.getElementById('progressBar').style.width = progress + '%';

        // 显示对应步骤内容
        document.querySelectorAll('.step-content').forEach(function(content) {
            content.classList.remove('active');
        });
        var targetContent = document.querySelector('.step-content[data-step="' + step + '"]');
        if (targetContent) {
            targetContent.classList.add('active');
        }

        currentStep = step;

        // 如果是第7步，更新预览
        if (step === 7) {
            updateReview();
        }
    };

    // 下一步
    window.nextStep = function(fromStep) {
        if (!validateStep(fromStep)) {
            return;
        }
        goToStep(fromStep + 1);
    };

    // 上一步
    window.prevStep = function(fromStep) {
        goToStep(fromStep - 1);
    };

    // 验证当前步骤
    function validateStep(step) {
        switch(step) {
            case 1:
                return validateStep1();
            case 2:
                return validateStep2();
            case 3:
                return validateStep3();
            case 4:
                return validateStep4();
            case 5:
                return validateStep5();
            case 6:
                return validateStep6();
            default:
                return true;
        }
    }

    // 身份证校验函数
    window.validateIdCard = function(idCard) {
        if (!idCard || idCard.length !== 18) return false;
        if (!/^\d{17}[\dXx]$/.test(idCard)) return false;

        var weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2];
        var checkCodes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2'];

        var sum = 0;
        for (var i = 0; i < 17; i++) {
            sum += parseInt(idCard[i]) * weights[i];
        }
        var expectedCheck = checkCodes[sum % 11];

        return idCard[17].toUpperCase() === expectedCheck;
    };

    // 步骤1验证
    function validateStep1() {
        var nameInput = document.getElementById('realName');
        var idCardInput = document.getElementById('idCard');
        var nameGroup = nameInput.parentElement;
        var idCardGroup = idCardInput.parentElement;

        // 姓名验证：2-20个汉字
        var nameValid = /^[\u4e00-\u9fa5]{2,20}$/.test(nameInput.value);
        // 身份证验证
        var idCardValid = window.validateIdCard(idCardInput.value);

        nameGroup.classList.toggle('error', !nameValid);
        idCardGroup.classList.toggle('error', !idCardValid);

        if (!nameValid) {
            nameInput.parentElement.querySelector('.error-text').textContent = '姓名格式不正确，需为2-20个汉字';
            nameInput.parentElement.querySelector('.error-text').style.display = 'block';
            return false;
        }
        
        if (!idCardValid) {
            document.getElementById('idCardError').textContent = '身份证号格式不正确或校验码错误';
            document.getElementById('idCardError').style.display = 'block';
            return false;
        }

        // 检查身份证是否已注册（异步）
        return fetch('/api/validate_id_card', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id_card: idCardInput.value})
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                formData.realName = nameInput.value;
                formData.idCard = idCardInput.value;
                return true;
            } else {
                idCardGroup.classList.add('error');
                document.getElementById('idCardError').textContent = data.message;
                document.getElementById('idCardError').style.display = 'block';
                return false;
            }
        })
        .catch(function() {
            return false;
        });
    }

    // 步骤2验证
    function validateStep2() {
        var emailInput = document.getElementById('email');
        var codeInput = document.getElementById('verifyCode');

        if (!formData.verified) {
            alert('请先完成邮箱验证');
            return false;
        }

        formData.email = emailInput.value;
        return true;
    }

    // 发送验证码
    window.sendCode = function() {
        var emailInput = document.getElementById('email');
        var email = emailInput.value.trim();

        if (!/^[\w\.-]+@[\w\.-]+\.\w+$/.test(email)) {
            alert('请输入正确的邮箱地址');
            return;
        }

        var btn = document.getElementById('sendCodeBtn');
        btn.disabled = true;
        btn.textContent = '发送中...';

        fetch('/api/send_code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: email})
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            btn.disabled = false;
            btn.textContent = '发送验证码';

            if (data.success) {
                // 开发模式显示验证码
                if (data.dev_code) {
                    devCode = data.dev_code;
                    document.getElementById('codeDisplay').style.display = 'block';
                    document.getElementById('devCodeDisplay').textContent = devCode;
                    document.getElementById('verifyCode').value = devCode;
                    formData.verified = true;
                } else {
                    alert('验证码已发送到您的邮箱');
                    startCountdown();
                }
            } else {
                alert(data.message);
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.textContent = '发送验证码';
            alert('发送失败，请重试');
        });
    };

    // 验证码倒计时
    var countdownTimer = null;
    function startCountdown() {
        var btn = document.getElementById('sendCodeBtn');
        var seconds = 60;

        countdownTimer = setInterval(function() {
            seconds--;
            if (seconds <= 0) {
                clearInterval(countdownTimer);
                btn.textContent = '发送验证码';
                btn.disabled = false;
            } else {
                btn.textContent = seconds + '秒后重试';
                btn.disabled = true;
            }
        }, 1000);
    }

    // 步骤3验证
    function validateStep3() {
        var stationCode = document.getElementById('stationSelect').value;

        if (!stationCode) {
            alert('请选择车站');
            return false;
        }

        formData.stationCode = stationCode;
        return true;
    }

    // 步骤4验证
    function validateStep4() {
        var lettersInput = document.getElementById('usernameLetters');
        var letters = lettersInput.value.trim().toUpperCase();

        if (!/^[A-Z]{2,3}$/.test(letters)) {
            lettersInput.parentElement.classList.add('error');
            lettersInput.parentElement.querySelector('.error-text').textContent = '必须输入2-3位大写字母';
            lettersInput.parentElement.querySelector('.error-text').style.display = 'block';
            return false;
        }

        lettersInput.parentElement.classList.remove('error');
        formData.usernameLetters = letters;
        formData.username = generateUsername(formData.stationCode, letters);
        return true;
    }

    // 生成工号预览
    window.generateUsername = function(stationCode, letters) {
        return stationCode + '-' + letters + '-001';
    };

    // 步骤5验证
    function validateStep5() {
        var windowNo = document.getElementById('selectedWindow').value;

        if (!windowNo) {
            alert('请选择窗口号');
            return false;
        }

        formData.windowNo = windowNo;
        return true;
    }

    // 选择窗口号
    window.selectWindow = function(windowNo) {
        var options = document.querySelectorAll('.window-option');
        options.forEach(function(opt) {
            opt.classList.remove('selected');
        });

        var selected = document.querySelector('.window-option[data-window="' + windowNo + '"]');
        if (selected && !selected.classList.contains('disabled')) {
            selected.classList.add('selected');
            document.getElementById('selectedWindow').value = windowNo;

            document.getElementById('windowStationName').textContent = formData.stationName + ' 售票窗口';
            document.getElementById('windowNoDisplay').textContent = windowNo + '号窗口';
            document.getElementById('windowDisplay').style.display = 'block';
        }
    };

    // 步骤6验证
    function validateStep6() {
        var passwordInput = document.getElementById('password');
        var confirmInput = document.getElementById('confirmPassword');
        var password = passwordInput.value;
        var confirm = confirmInput.value;

        var passwordGroup = passwordInput.parentElement;
        var confirmGroup = confirmInput.parentElement;

        // 密码格式：8-20位，包含字母和数字
        var passwordValid = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,20}$/.test(password);
        var confirmValid = password === confirm && password.length > 0;

        if (!passwordValid) {
            passwordInput.parentElement.classList.add('error');
            passwordInput.parentElement.querySelector('.error-text').textContent = '密码8-20位，必须包含字母和数字';
            return false;
        }
        
        passwordInput.parentElement.classList.remove('error');

        if (!confirmValid) {
            confirmInput.parentElement.classList.add('error');
            confirmInput.parentElement.querySelector('.error-text').textContent = '两次密码不一致';
            return false;
        }
        
        confirmInput.parentElement.classList.remove('error');

        formData.password = password;
        return true;
    }

    // 更新审核预览
    function updateReview() {
        document.getElementById('reviewName').textContent = formData.realName;
        document.getElementById('reviewIdCard').textContent = maskIdCard(formData.idCard);
        document.getElementById('reviewEmail').textContent = formData.email;
        document.getElementById('reviewStation').textContent = formData.stationName + ' (' + formData.stationCode + ')';
        document.getElementById('reviewUsername').textContent = formData.username;
        document.getElementById('reviewWindow').textContent = formData.windowNo + '号窗口';
    }

    function maskIdCard(idCard) {
        if (idCard.length === 18) {
            return idCard.slice(0, 3) + '**********' + idCard.slice(-4);
        }
        return idCard;
    }

    // 提交注册
    window.submitRegister = function() {
        var submitBtn = document.getElementById('submitBtn');
        var loading = document.getElementById('loading');

        submitBtn.style.display = 'none';
        loading.classList.add('active');

        // 获取机器码
        FingerprintJS.get(function(err, result) {
            if (err || !result) {
                loading.classList.remove('active');
                submitBtn.style.display = 'block';
                alert('获取机器码失败，请刷新页面重试');
                return;
            }

            var machineCode = result.hash;

            var data = {
                real_name: formData.realName,
                id_card: formData.idCard,
                email: formData.email,
                station_code: formData.stationCode,
                username: formData.username,
                window_no: formData.windowNo,
                password: formData.password,
                machine_code: machineCode,
                code_verified: devCode || formData.verified
            };

            fetch('/api/submit_register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                loading.classList.remove('active');

                if (data.success) {
                    // 显示成功页面
                    document.querySelector('.step-content[data-step="7"]').classList.remove('active');
                    document.querySelector('.step-content[data-step="success"]').classList.add('active');
                    document.getElementById('progressBar').style.width = '100%';

                    // 更新所有步骤指示器为完成
                    document.querySelectorAll('.step-circle').forEach(function(c) {
                        c.classList.remove('active');
                        c.classList.add('completed');
                    });
                } else {
                    submitBtn.style.display = 'block';
                    alert(data.message);
                }
            })
            .catch(function() {
                loading.classList.remove('active');
                submitBtn.style.display = 'block';
                alert('提交失败，请重试');
            });
        });
    };

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        // 初始化步骤指示器
        goToStep(1);

        // 车站搜索输入处理
        var stationSearch = document.getElementById('stationSearch');
        if (stationSearch) {
            stationSearch.addEventListener('input', function() {
                var keyword = this.value.trim();

                clearTimeout(searchTimeout);

                if (keyword.length < 1) {
                    return;
                }

                searchTimeout = setTimeout(function() {
                    fetch('/api/search_stations?q=' + encodeURIComponent(keyword))
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            var select = document.getElementById('stationSelect');
                            select.innerHTML = '<option value="">-- 选择车站 --</option>';

                            data.forEach(function(station) {
                                var option = document.createElement('option');
                                option.value = station.telecode || station.station_code;
                                option.textContent = station.station_name + ' (' + (station.telecode || station.station_code) + ')';
                                option.dataset.name = station.station_name;
                                select.appendChild(option);
                            });
                        });
                }, 300);
            });
        }

        // 车站选择处理
        var stationSelect = document.getElementById('stationSelect');
        if (stationSelect) {
            stationSelect.addEventListener('change', function() {
                var selected = this.options[this.selectedIndex];
                var display = document.getElementById('stationDisplay');

                if (this.value) {
                    formData.stationCode = this.value;
                    formData.stationName = selected.dataset.name;

                    document.getElementById('selectedStationName').textContent = selected.dataset.name;
                    document.getElementById('selectedStationCode').textContent = '电报码: ' + this.value;
                    display.style.display = 'block';

                    // 更新工号预览
                    var letters = document.getElementById('usernameLetters').value.trim().toUpperCase();
                    if (letters) {
                        var username = generateUsername(this.value, letters);
                        document.getElementById('previewUsername').textContent = username;
                        formData.username = username;
                    } else {
                        document.getElementById('previewUsername').textContent = this.value + '- -- -001';
                    }
                } else {
                    display.style.display = 'none';
                }
            });
        }

        // 工号字母输入处理
        var usernameLetters = document.getElementById('usernameLetters');
        if (usernameLetters) {
            usernameLetters.addEventListener('input', function() {
                var letters = this.value.trim().toUpperCase();
                var preview = document.getElementById('previewUsername');

                if (/^[A-Z]{2,3}$/.test(letters)) {
                    var username = generateUsername(formData.stationCode, letters);
                    preview.textContent = username;
                    formData.usernameLetters = letters;
                    formData.username = username;
                    this.parentElement.classList.remove('error');
                } else if (letters.length > 0) {
                    preview.textContent = formData.stationCode ? formData.stationCode + '-' + letters + '-001' : '-- - -- ---';
                    this.parentElement.classList.add('error');
                    this.parentElement.querySelector('.error-text').textContent = '必须输入2-3位大写字母';
                } else {
                    preview.textContent = formData.stationCode ? formData.stationCode + '- -- -001' : '-- - -- ---';
                    this.parentElement.classList.remove('error');
                }
            });
        }

        // 验证码输入框回车提交
        var verifyCode = document.getElementById('verifyCode');
        if (verifyCode) {
            verifyCode.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    var email = document.getElementById('email').value.trim();
                    var code = this.value.trim();
                    
                    if (email && code && code.length === 6) {
                        // 自动验证
                        fetch('/api/verify_code', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({email: email, code: code})
                        })
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            if (data.success) {
                                formData.verified = true;
                                alert('验证成功');
                            } else {
                                document.getElementById('codeError').style.display = 'block';
                            }
                        });
                    }
                }
            });
        }
    });

})(window);
